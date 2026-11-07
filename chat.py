"""Terminal chat with a local model that can search the offline library.

Usage: chat.py [--model NAME] [--dutch] [question ...]   (default: the first chat model Ollama has; --dutch: answers in Dutch)
With a question it answers once and exits; without one it opens a chat.
In a chat: /sources lists what the last answer used, /open N opens one, /reasoning shows its reasoning, /new,
/think off|short|medium|long|none sets how much it may reason before answering, /limit normal|long|none sets how long
an answer may run, /bye.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
from core import LENGTH_LIMITS, REASONING_LIMITS, capabilities, chat_events, installed_models, system_prompt, trim  # noqa: E402
from library.search import DB_PATH, Library  # noqa: E402

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def open_article(library, passage_id):
    """Write the article to a Markdown file, marking the cited passage, and open it."""
    doc = library.document(passage_id)
    if not doc:
        return
    lines = [f"# {doc['title']}", f"Source: {doc['source']}" + (f" | {doc['url']}" if doc["url"] else ""), ""]
    for part in doc["parts"]:
        if part["id"] == passage_id:
            lines += ["", ">>> THE PASSAGE THE ANSWER CAME FROM <<<", ""]
        lines.append(part["text"])
        lines.append("")
    path = os.path.join(tempfile.gettempdir(), f"survival-llm-article-{doc['doc_id']}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if sys.platform == "darwin":
        subprocess.run(["open", "-t", path])
    elif os.name == "nt":
        os.startfile(path)
    else:
        subprocess.run(["xdg-open", path])
    print(f"{DIM}  · opened: {doc['title']} ({doc['source']}){RESET}")


def run_turn(model, library, messages, level, caps, length="normal"):
    """Print one answer as it streams; returns the sources it used and its reasoning (for /reasoning)."""
    sources, reasoning = [], []  # reasoning: what it thought, with its lookups in between
    fresh = True  # nothing printed since the last lookup; skip the blank lines models emit before tool calls
    thinking, thoughts = False, 0  # in a stretch of reasoning; how many stretches
    for ev in chat_events(model, library, messages, reasoning=level, caps=caps, length=length):
        kind = ev["type"]
        if kind not in ("token", "tick"):
            fresh = True
        if kind != "tick":
            thinking = thinking and kind == "thinking"
        if kind == "thinking":
            if not thinking and ev["text"].strip():
                print(f"{DIM}  · thinking{'' if thoughts else ' (/reasoning shows it)'}{RESET}", flush=True)
                reasoning.append("")
                thinking, thoughts = True, thoughts + 1
            if thinking:
                reasoning[-1] += ev["text"]
        elif kind == "search":
            topic = f" [{ev['topic']}]" if ev["topic"] != "any" else ""
            print(f"{DIM}  · searching: {ev['query']}{topic}{RESET}", flush=True)
            reasoning.append(f"· searching: {ev['query']}{topic}")
        elif kind == "read":
            print(f"{DIM}  · reading: {ev['title']} ({ev['source']}){RESET}", flush=True)
            reasoning.append(f"· reading: {ev['title']} ({ev['source']})")
        elif kind == "think_limit":
            print(f"{DIM}  · its thinking reached the limit; answering from what it has{RESET}", flush=True)
            reasoning.append("· thinking reached the limit")
        elif kind == "retry":
            print(f"{DIM}  · {'asked to search, as you asked' if ev.get('why') == 'search' else 'answering from the articles it found'}"
                  f"{RESET}", flush=True)
        elif kind == "show":
            open_article(library, ev["id"])
            reasoning.append(f"· opened: {ev['title']} ({ev['source']})")
        elif kind == "token":
            if fresh and not ev["text"].strip():
                continue
            fresh = False
            print(ev["text"], end="", flush=True)
        elif kind == "done":
            sources = ev["sources"]
            speed = f" · {ev['tokens'] / ev['seconds']:.0f} tok/s" if ev["seconds"] else ""
            note = " · /sources to see what it read" if sources else ""
            if ev.get("cut_off"):
                print(f"\n{DIM}[stopped: the answer ran too long; try asking again]{RESET}")
            elif ev.get("unfinished"):
                print(f"\n{DIM}[it kept looking things up and did not finish; try asking again]{RESET}")
            print(f"\n{DIM}[{ev['tokens']} tokens{speed}{note}]{RESET}")
    return sources, "\n\n".join(r.strip() for r in reasoning if r.strip()) if thoughts else ""


def main():
    args = sys.argv[1:]
    model = None
    if args[:1] == ["--model"]:
        model, args = args[1], args[2:]
    if args[:1] == ["--dutch"]:
        core.set_language("nl")
        args = args[1:]
    if not model:
        names = [m for m in installed_models() or [] if not any(x in m for x in ("embed", "bge-", "nomic", "minilm"))]
        if not names:
            sys.exit("No AI model found. Start Ollama, download a model (ollama pull granite4.2:8b), or use --model.")
        model = names[0]
    library = None
    if os.path.exists(DB_PATH):
        try:
            library = Library()
            if library.stats()[0] == 0:
                library = None
        except Exception:
            library = None
    caps = capabilities(model)
    lang = core.LANGUAGE_PROMPTS.get(core.language[0])
    messages = [{"role": "system", "content": system_prompt(library, "tools" in caps) + (f"\n\n{lang}" if lang else "")}]
    level, length = "off", "normal"  # the Reasoning setting, and the length limit

    if args:  # one question, one answer
        messages.append({"role": "user", "content": " ".join(args)})
        run_turn(model, library, messages, level, caps)
        return

    try:
        import readline  # noqa: F401  (arrow keys and history in input())
    except ImportError:
        pass
    docs, n_sources = library.stats() if library else (0, 0)
    lib_note = f"library: {docs:,} articles from {n_sources} sources" if library else "no library found"
    print(f"{BOLD}{model.removesuffix(':latest')}{RESET} {DIM}· offline · {lib_note}{RESET}")
    print(f"{DIM}Ask anything. /sources shows what the last answer read, /open N opens one, /reasoning shows how it "
          f"reasoned, /new starts over, /think sets how much it may reason, /limit sets the answer length limit, /bye quits.{RESET}")
    last_sources, last_reasoning = [], ""
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        if question in ("/bye", "/quit", "/exit"):
            return
        if question == "/new":
            messages, last_sources = messages[:1], []
            print(f"{DIM}Started over.{RESET}")
            continue
        if question.startswith("/think"):
            pick = question[6:].strip()
            if pick in REASONING_LIMITS:
                level = pick
                budget = REASONING_LIMITS[pick]
                print(f"{DIM}Reasoning: {pick}" + (f" (up to {budget:,} tokens, then it answers)" if budget > 0 else
                      " (no limit; Ctrl+C stops a model stuck reasoning in circles)" if budget < 0 else "") + f".{RESET}")
            else:
                print(f"{DIM}Use /think off, short, medium, long or none (now: {level}).{RESET}")
            continue
        if question.startswith("/limit"):
            pick = question[6:].strip()
            if pick in LENGTH_LIMITS:
                length = pick
                print(f"{DIM}Length limit: {pick}{' (use Ctrl+C to stop a stuck answer)' if pick == 'none' else ''}.{RESET}")
            else:
                print(f"{DIM}Use /limit normal, /limit long or /limit none (now: {length}).{RESET}")
            continue
        if question == "/reasoning":
            print(f"{DIM}{last_reasoning}{RESET}" if last_reasoning else
                  f"{DIM}The last answer had no reasoning. /think makes the model reason before it answers.{RESET}")
            continue
        if question == "/sources":
            if not last_sources:
                print(f"{DIM}The last answer did not read anything from the library.{RESET}")
            for n, s in enumerate(last_sources, 1):
                print(f"  {n}. {s['title']} ({s['source']})")
            continue
        if question.startswith("/open"):
            pick = question[5:].strip() or "1"
            if pick.isdigit() and 1 <= int(pick) <= len(last_sources) and library:
                open_article(library, last_sources[int(pick) - 1]["id"])
            else:
                print(f"{DIM}Use /open N, where N is a number from /sources.{RESET}")
            continue
        messages.append({"role": "user", "content": question})
        trim(messages)
        print()
        last_reasoning = ""
        try:
            used, last_reasoning = run_turn(model, library, messages, level, caps, length)
            last_sources = used or last_sources
        except KeyboardInterrupt:
            print(f"\n{DIM}[stopped]{RESET}")
        except OSError as exc:
            print(f"\n{DIM}[could not reach the local model: {exc}. Is Ollama running? Try: ollama serve]{RESET}")


if __name__ == "__main__":
    main()
