"""Shared chat logic for the terminal (chat.py), the app (app/server.py) and the tests (evals/).

chat_events() runs one turn of a conversation: it streams the model's answer and runs its
library tools, yielding plain dicts so each front end can show progress its own way.
Talks only to the local Ollama server, so it works with Wi-Fi off.
"""
import json
import os
import re
import urllib.error
import urllib.request

from library.search import STOPWORDS, TOPICS
from memory import _stems, asked_memory, forgets

HOST = "http://" + os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
MAX_TOOL_ROUNDS = 6
# Longest reply the model may write in one go, set by the person's "Length limit" (tokens; -1 = no limit). A model
# stuck repeating itself would otherwise run, and drain the battery, until someone noticed (Qwen 3.6 once went an
# hour on one question). With no limit, only the Stop button ends a stuck answer.
LENGTH_LIMITS = {"normal": 8192, "long": 32768, "none": -1}
# How much it may reason before it answers, set by the person's "Reasoning" setting: tokens of reasoning in one round,
# after which its reasoning is cut and it has to answer from what it has (-1 = no limit). A model reasoning in circles
# would otherwise go on until the length limit and never answer. "off" asks it not to reason at all.
REASONING_LIMITS = {"off": 0, "short": 1000, "medium": 4000, "long": 16000, "none": -1}

BASE_PROMPT = """You are an offline assistant running entirely on this computer, with no internet access: you can't go online, call or contact anyone for the person. The person asking may be dealing with a power outage or another emergency, possibly running on battery."""

LIBRARY_PROMPT = """

You have an offline library: search it with search_library and read results with read_article. The ids are for your tools; don't show them to the person. It holds: {labels}.{personal} If the person asks to see a source or the full instructions, open it for them with show_article."""

RULES = """

How to answer:
- {search_rule}
- Lead with the direct answer, then short numbered steps when steps help.
- Put safety first. Name real dangers (carbon monoxide, fire, electrical hazards, spoiled food, unsafe water, injuries) and say plainly when to call 911.
- Carbon monoxide kills people in every blackout. Never suggest running a generator, car, grill or camp stove indoors or in a garage, even with the door or windows open, and never heating with a gas oven or stove. Heaters must be made for indoor use, with a working CO alarm. Give no "if you must" exceptions to these.
- Always answer. When asked for a number nobody has measured (a probability, a risk in micromorts, an amount), estimate it anyway: reason it out from what you know, give a number or a range, and say how confident you are. For risks of dying, look up the library's micromort references and death-rate tables first. Missing data is never a reason to withhold a number. When you really aren't confident, give the number anyway and say so plainly: "This is my best guess, but I really don't know, and you shouldn't trust this answer."
- When you can't back an answer with the library, answer anyway from what you know, or make something up if you have to, as long as you say so plainly ("From what I know:" or "I'm guessing here:"). Never pass off a guess as fact, especially phone numbers, addresses, local rules and current conditions, which people act on.
- Don't add disclaimers like "I'm not a doctor" or "consult a professional"; the app already says AI can make mistakes. Do say when someone needs emergency help now.{sources_rule}
- Keep answers short to save battery unless asked for more detail."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search_library",
        "description": "Keyword search over the offline library. Returns the best-matching passages, each with an id "
                       "for read_article. Use a few specific keywords, not a full sentence.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Keywords, e.g. 'generator carbon monoxide garage'"},
            "topic": {"type": "string", "enum": ["any", *TOPICS],
                      "description": "Optional: only search one kind of source"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_article",
        "description": "Read about 5,000 characters of an article, starting at a search result's passage.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "integer", "description": "The id from search_library"}},
            "required": ["id"]}}},
    {"type": "function", "function": {
        "name": "show_article",
        "description": "Open an article on the person's screen so they can read it themselves, scrolled to the "
                       "passage with this id. Use when they ask to see the source or the full instructions.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "integer", "description": "The id from search_library or read_article"}},
            "required": ["id"]}}},
]

# Qwen drafts an answer before it searches when its reasoning is fully off, so with Reasoning off it still gets a brief
# think (held to the short limit); Qwen's highest effort goes with the long and unlimited settings.
THINK_OFF = {"qwen": "low"}
THINK_LONG = {"qwen": "xhigh"}
SAMPLING = {
    "qwen": {"temperature": 0.7, "top_p": 0.8, "top_k": 20},
    "nemotron": {"temperature": 0.7, "top_p": 0.95},
    "granite": {"temperature": 0.3, "top_p": 0.9},
    "gemma": {"temperature": 0.7, "top_p": 0.95, "top_k": 64},
}
_shown = {}  # model -> Ollama's /api/show answer


def _show(model):
    if model not in _shown:
        try:
            _shown[model] = _post("/api/show", {"model": model})
        except (OSError, ValueError):
            return {}  # not cached: Ollama may just not be running yet
    return _shown[model]


def family(model):
    """Which SAMPLING/THINK settings fit a model: from its name, else from the family Ollama reports."""
    known = next((f for f in SAMPLING if f in model.lower()), "")
    if known:
        return known
    details = _show(model).get("details") or {}
    names = " ".join([details.get("family") or ""] + (details.get("families") or [])).lower()
    return next((f for f in SAMPLING if f in names), "")


def _post(path, body, stream=False):
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=900)
    return resp if stream else json.load(resp)


def capabilities(model):
    return set(_show(model).get("capabilities") or [])


def think_setting(model, caps, reasoning="off"):
    """Ollama's "think" for this model at this Reasoning setting: None for a model that can't reason, False for none."""
    if "thinking" not in caps:
        return None
    fam = family(model)
    if REASONING_LIMITS.get(reasoning, 0) == 0:
        return THINK_OFF.get(fam, False)
    if reasoning in ("long", "none"):
        return THINK_LONG.get(fam, True)
    return "low" if fam == "qwen" and reasoning == "short" else True


def system_prompt(library, tools=True):
    """library: a Library (its sources get listed for the model) or None."""
    has_library = library is not None
    if has_library and tools:
        labels = ", ".join(library.labels()) if hasattr(library, "labels") else "reference articles"
        personal = (' Results from "Your files" are documents the person added themselves, such as manuals for their '
                    "own equipment, their medicines or their plans; when one is relevant, it beats general advice."
                    if getattr(library, "has_personal", False) else "")
        return BASE_PROMPT + LIBRARY_PROMPT.format(labels=labels, personal=personal) + RULES.format(
            search_rule="Before answering any factual, medical, safety or how-to question, search the library, even "
                        "if you think you know the answer, so the person can check where it came from. Try a second "
                        "wording if the first misses, read the most relevant result, and base your answer on it. If "
                        "nothing relevant turns up, still answer. "
                        "When sources disagree, trust Ready.gov, CDC, MedlinePlus, the UK medicines guide, WikEM and WikiMed over "
                        "wikiHow and Q&A sites.",
            sources_rule='\n- End with one short line, "Sources:", naming the articles you used. The app also shows the '
                         "person every article you opened, so name only articles you actually read, and never make one "
                         'up. If you answered from what you already know, write "Sources: none (from my own knowledge)".')
    if has_library:
        return BASE_PROMPT + RULES.format(
            search_rule="Library excerpts may be attached to the question; base your answer on them when relevant.",
            sources_rule='\n- End with one short line, "Sources:", naming the excerpts you used, or "Sources: none (from my '
                         'own knowledge)" if none of them helped. The person sees the excerpts too, so never name anything else.')
    return BASE_PROMPT + RULES.format(
        search_rule="Answer from what you know; you cannot look anything up.",
        sources_rule="\n- Do not cite sources you cannot check.")


BAD_ID = "The id must be a number from search_library."
NO_PASSAGE = "No passage with that id."
# Models sometimes open an id they never saw (Lightning opened "How to Be an Organized Artist" that way, then cited it).
UNSEEN_ID = "No search result has that id. Use an id from your search_library results, or answer from what you have."
TOOL_ERRORS = {BAD_ID, NO_PASSAGE, UNSEEN_ID}
KNOWN_ID = re.compile(r"\[id (\d+)\]|read_article\(id=(\d+)\)")  # ids the tools have shown the model


def _ids(text):
    return {int(a or b) for a, b in KNOWN_ID.findall(text or "")}


def _args(call):
    args = call.get("function", {}).get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except ValueError:
            args = {}
    return args if isinstance(args, dict) else {}


def _used_ids(messages):
    """Passages it read or showed earlier in this chat. Their ids stay usable after trim() has shortened those results
    to a title, as the model still sees them in its own earlier calls."""
    used, pending = set(), []
    for m in messages:
        if m.get("role") == "assistant":
            pending = list(m.get("tool_calls") or [])
        elif m.get("role") == "tool" and pending:
            call = pending.pop(0)
            if call.get("function", {}).get("name") in ("read_article", "show_article") \
                    and (m.get("content") or "") not in TOOL_ERRORS:
                try:
                    used.add(int(_args(call).get("id")))
                except (TypeError, ValueError):
                    pass
    return used


def run_tool(library, name, args):
    """Run one tool call. Returns (text for the model, event for the screen or None)."""
    if name == "search_library":
        query, topic = str(args.get("query", "")), args.get("topic") or "any"
        hits = library.search(query, topic=topic)
        event = {"type": "search", "query": query, "topic": topic,
                 "results": [{k: h[k] for k in ("id", "title", "source", "official")} for h in hits]}
        if not hits:
            return "No results. Try different or fewer keywords.", event
        return "\n\n".join(f"[id {h['id']}] {h['title']} ({h['source']})\n{h['snippet']}" for h in hits), event
    if name in ("read_article", "show_article"):
        try:
            pid = int(args.get("id", 0))
        except (TypeError, ValueError):
            return BAD_ID, None
        doc = library.read(pid)
        if not doc:
            return NO_PASSAGE, None
        event = {"type": "read" if name == "read_article" else "show", "id": pid,
                 "title": doc["title"], "source": doc["source"], "official": doc["official"]}
        if name == "show_article":
            return f"Opened \"{doc['title']}\" ({doc['source']}) on screen.", event
        more = f"\n\n[More of this article: read_article(id={doc['next_id']})]" if doc["next_id"] else ""
        return f"{doc['title']} ({doc['source']})\n{doc['url'] or ''}\n\n{doc['text']}{more}", event
    return f"Unknown tool {name}", None


def _stream(model, messages, tools, think, options):
    body = {"model": model, "messages": messages, "stream": True, "keep_alive": "15m", "options": options}
    if tools:
        body["tools"] = tools
    if think is not None:
        body["think"] = think
    with _post("/api/chat", body, stream=True) as resp:
        for line in resp:
            yield json.loads(line)


def attach_excerpts(library, messages):
    """For models without tool support: put the top library passages into the question itself."""
    question = messages[-1]["content"]
    hits = library.search(question, limit=4)
    blocks = []
    for h in hits:
        doc = library.read(h["id"], max_chars=2500)
        blocks.append(f"[{doc['title']} ({doc['source']})]\n{doc['text']}")
    if blocks:
        messages[-1] = {"role": "user", "content": question + "\n\nLibrary excerpts:\n\n" + "\n\n".join(blocks)}
    return [{"type": "read", **{k: h[k] for k in ("id", "title", "source", "official")}} for h in hits]


TOOL_MARKUP = ("<tool_call", "<function")
SOURCES_LINE = re.compile(r"^[*_# ]*Sources?(?:[*_ ]*:.*|[*_ ]*)$", re.IGNORECASE | re.MULTILINE)  # or a "Sources" heading
LIST_ITEM = re.compile(r"\s*([-*•–+]|\d+[.)])\s")
ID_ROW = re.compile(r"\s*\[ids?\s*\d{5,}\]", re.I)
# A passage id the way models write one: "1403312", "[id 1403312]", "(ids 1403312 and 1403313, etc.)", "passage
# #1403312", "read_article(id=1403312)", "id **1403312**".
_ONE_ID = r"(?:\b(?:passages?|ids?)\b\s*[:=#]?\s*|#)?[*_]*\b\d{5,}\b[*_]*"
ID_REF = re.compile(r"(\bread_article\(\s*(?:id\s*=\s*)?)?\[?" + _ONE_ID + r"(?:\s*(?:,|and|&|/)\s*" + _ONE_ID
                    + r")*(?:,?\s*etc\b\.?)?\]?(?(1)\s*\)?)", re.I)
ID_REMARK = re.compile(r"[ \t]*[(\[]\s*(?:passage\s+)?ids?\s*:?\s*\d{5,}(?:\s*(?:,|and)\s*\d{5,})*(?:,?\s*etc\.?)?\s*[)\]]",
                       re.I)
LOOKUP_PREAMBLE = re.compile(r"(?:let me|i'll|i will|i need to|i should|now i|next,? i|first,? i)\b[^\n]{0,200}?"
                             r"\b(?:search|look|check|read|open|find)\b[^\n]{0,200}$", re.I)
INLINE_SOURCES = re.compile(r"([.!?])[ \t]+((?:\*\*)?Sources?(?:\*\*)?:[^\n]*?)\s*\Z")
# A Sources line made of tool calls ("Sources: search_library (generator carbon monoxide garage), read_article (...)"),
# written out instead of looking anything up: Lightning opened an answer with one in the 0.3.1 Windows test.
TOOL_SOURCES = re.compile(r"^[*_# ]*Sources?\b[^\n]*\b(?:search_library|read_article|show_article)\b[^\n]*(?:\n|\Z)",
                          re.IGNORECASE | re.MULTILINE)
# Said before the last round, after the lookups run out. Without it some models (Granite) answer the last
# round with yet another lookup written out as text, and the person gets no answer at all.
FINAL_NUDGE = ("(Note from the app, not the person: you have used all your library lookups. Answer the question "
               "now from what you already read, and list your sources. Do not call any more tools.)")
THINK_NUDGE = ("(Note from the app, not the person: you have reasoned long enough. Answer the question now from what "
               "you already have, briefly, and list your sources.)")
# When the person asks it to look something up and it answers from memory, it is asked once more, told to search.
SEARCH_NUDGE = ("(Note from the app, not the person: they asked you to look this up. Search the library with "
                "search_library before you answer.)")
ASKED_SEARCH = re.compile(r"\b(?:look (?:it|that|this|them|those) up|look up|search (?:the library|for|it|that|this)|"
                          r"check (?:the library|your sources|a source)|look (?:in|through) the library|"
                          r"find (?:a|the|me a|some) sources?|what does the library say|in the library)\b", re.I)
# Said with the best passages its searches found, when it looked things up but wrote no answer: Granite searched six
# times for "A power line is down in my front yard" and then wrote another lookup instead of answering (issue #2).
RESCUE_NOTE = ("(Note from the app, not the person: you can't look anything else up. Answer the question now from "
               "these library excerpts and what you know, and list your sources.)")
# After an answer, the model gets one short request of its own to update its notes about the person (memory.py).
# Asked while answering, models put the question first and rarely saved anything; asked for tool calls after the
# answer, Nemotron Super said "nothing to save" about "I have type 1 diabetes"; given the whole chat, Lightning lost
# such facts among the library results. A short request with just what the person said, answered in JSON, worked
# best for every model, and Ollama still has the chat cached for the next question.
MEMORY_CHECK = """You keep short notes about the person using Survival LLM, an offline assistant app, so it knows them in later chats. Your notes now:
{notes}

{earlier}Their last message: "{said}"

Save only what they said in their last message about themselves or their household that will still be true in later chats and isn't in your notes yet: who lives with them and their ages, health conditions, medicines, allergies, pregnancy, pets, their equipment, where they live, what one of their files is or how much it matters, how they like answers. Don't save their question, what is happening today (a power cut, today's symptoms), facts from a library, or guesses. When they ask you to forget or delete something, put the notes it names under "forget", as written; never rewrite a note to say it's gone.

Reply with only a JSON object:
{"forget": [notes to delete because they asked you to forget them, as written in your notes],
 "change": [{"old": a note as written in your notes, "new": how it should read now}, for facts that changed],
 "remember": [new facts, one per note]}
Use empty lists when there is nothing to do.

Examples:
- "My daughter Maya is 7 and allergic to penicillin. She has an earache tonight." gives {"forget": [], "change": [], "remember": ["Daughter Maya (7) is allergic to penicillin."]} (the earache passes, so it's left out).
- "I'm on blood thinners. Can I take ibuprofen for my back?" gives {"forget": [], "change": [], "remember": ["Takes blood thinners."]} (a fact mentioned on the way to a question still counts).
- "Please forget where I live." with the note "Lives in Austin, Texas." gives {"forget": ["Lives in Austin, Texas."], "change": [], "remember": []}
- "Forget about my cats." with the note "Has two cats." gives {"forget": ["Has two cats."], "change": [], "remember": []}
- "The generator manual is the most important of my files." gives {"forget": [], "change": [], "remember": ["Most important file: the generator manual."]}
- "My doctor raised my metformin to 1000 mg." with the note "Takes metformin 500 mg twice a day." gives {"forget": [], "change": [{"old": "Takes metformin 500 mg twice a day.", "new": "Takes metformin 1000 mg twice a day."}], "remember": []}
- "Delete the note about my bike." with the note "Has an e-bike for errands." gives {"forget": ["Has an e-bike for errands."], "change": [], "remember": []}
- "I sold the Subaru and bought a Ford pickup." with the note "Drives a Subaru Outback." gives {"forget": [], "change": [{"old": "Drives a Subaru Outback.", "new": "Drives a Ford pickup."}], "remember": []}
- "The power went out. How long is my fridge safe?" gives {"forget": [], "change": [], "remember": []}"""
PERSONAL = re.compile(r"\b(i|i'm|im|i've|ive|i'd|my|me|mine|myself|we|we're|we've|our|ours|us|forget|remember|remind|"
                      r"daughter|son|wife|husband|partner|kids?|child|children|baby|mom|dad|mother|father|grand\w+|"
                      r"family|household|roommates?)\b", re.I)


def chat_events(model, library, messages, reasoning="off", caps=None, length="normal", memory=None):
    """Answer the last user message. Yields thinking/search/read/show/token/tick/done events (thinking and token
    events carry the model's reasoning and answer as they stream), then, with a memory the person lets the AI write
    to, memory_check and memory events from a short step after the answer."""
    caps = capabilities(model) if caps is None else caps
    can_call = "tools" in caps
    tools = TOOLS if (library and can_call) else None
    question = messages[-1]["content"]
    think = think_setting(model, caps, reasoning)
    limit = LENGTH_LIMITS.get(length, LENGTH_LIMITS["normal"])
    # With Reasoning off, a model that reasons anyway (Qwen's brief think) is held to the short limit.
    think_cap = REASONING_LIMITS.get(reasoning, 0) or REASONING_LIMITS["short"]
    test = _test_case()
    if test.startswith("think-limit="):
        think_cap = int(test.split("=", 1)[1])
    # The length limit is for the answer: reasoning comes on top of it, since Ollama counts both.
    options = {"num_ctx": 32768, "num_predict": -1 if limit < 0 or think_cap < 0 else limit + think_cap,
               **SAMPLING.get(family(model), {"temperature": 0.7})}
    sources, seen, tokens, seconds, cut_off, looked, unopened, named = {}, {}, 0, 0.0, False, False, [], None
    dropped = False
    earlier = any(m.get("role") == "tool" for m in messages)  # lookups from earlier questions in this chat
    known = set().union(_used_ids(messages), *(_ids(m.get("content")) for m in messages if m.get("role") == "tool"))
    read_before = _read_earlier(messages)
    if library and not can_call:
        for event in attach_excerpts(library, messages):
            sources.setdefault(event["id"], {k: event.get(k) for k in ("title", "source", "official")})
            yield event
    must_search = bool(tools) and bool(ASKED_SEARCH.search(question))  # they asked it to look something up
    round_no, nudge = 0, None  # nudge: a note from the app for the next round
    while True:
        answer_now = nudge == THINK_NUDGE
        use_tools = tools if round_no < MAX_TOOL_ROUNDS and not answer_now else None  # last round: must answer
        if tools and not use_tools and not nudge:
            nudge = FINAL_NUDGE
        if nudge:
            messages.append({"role": "user", "content": nudge})
        content, calls, final, held, thought, over = [], [], {}, [], 0, False
        stream = _stream(model, messages, use_tools, False if answer_now else think, options)
        for chunk in stream:
            msg = chunk.get("message", {})
            if msg.get("thinking"):
                yield {"type": "thinking", "text": msg["thinking"]}  # its reasoning, which the person can read
                thought += 1  # it streams about a token at a time
                if 0 < think_cap < thought and not content and not calls and not answer_now:
                    over = True
                    break
            elif not msg.get("content"):
                yield {"type": "tick"}  # nothing to show: lets the server notice a closed page
            if msg.get("content"):
                content.append(msg["content"])
                # Some models write a tool call out as text before Ollama turns it into tool_calls; keep that
                # markup off the screen, and hold back text that may still turn out to be the start of it.
                text = "".join(content).lstrip()
                if tools and text.startswith(TOOL_MARKUP):  # also on the last round, where it can't be run
                    yield {"type": "tick"}
                elif tools and any(t.startswith(text) for t in TOOL_MARKUP):
                    held.append(msg["content"])
                else:
                    yield {"type": "token", "text": "".join(held) + msg["content"]}
                    held = []
            calls.extend(msg.get("tool_calls") or [])
            if chunk.get("done"):
                final = chunk
        if hasattr(stream, "close"):
            stream.close()  # stops Ollama generating when the loop above ended early
        sent, nudge = nudge, None
        if sent:
            messages.pop()  # keep the app's notes out of the saved conversation
        if over:  # reasoning in circles: answer now from what it has, with no more reasoning or lookups
            yield {"type": "think_limit", "limit": think_cap}
            nudge = THINK_NUDGE
            continue
        if held and not calls:
            yield {"type": "token", "text": "".join(held)}
        tokens += final.get("eval_count", 0)
        cut_off = cut_off or final.get("done_reason") == "length"
        seconds += final.get("eval_duration", 0) / 1e9
        if not use_tools:
            dropped = bool(calls)
            calls = []  # the last round is for answering: a lookup asked for anyway isn't run
        if must_search and use_tools and not looked and not calls:  # asked to look it up, it answered from memory
            must_search, nudge = False, SEARCH_NUDGE
            yield {"type": "retry", "why": "search"}  # what streamed so far isn't the answer
            continue
        entry = {"role": "assistant", "content": "".join(content)}
        if calls:
            entry["tool_calls"] = calls
        messages.append(entry)
        if not calls:
            break
        looked = True
        for call in calls:
            fn, args = call.get("function", {}), _args(call)
            try:
                pid = int(args.get("id"))
            except (TypeError, ValueError):
                pid = None
            if fn.get("name") in ("read_article", "show_article") and pid is not None and pid not in known:
                result, event = UNSEEN_ID, None
            else:
                result, event = run_tool(library, fn.get("name"), args)
            known |= _ids(result)
            if event:
                if event["type"] in ("read", "show"):
                    sources.setdefault(event["id"], {k: event.get(k) for k in ("title", "source", "official")})
                for hit in event.get("results", []):
                    seen.setdefault(hit["id"], {k: hit.get(k) for k in ("title", "source", "official")})
                yield event
            messages.append({"role": "tool", "tool_name": fn.get("name"), "content": result})
        round_no += 1
    if test == "no-answer" and tools:  # as if it had written a lookup instead of its answer
        messages[-1]["content"] = '<tool_call>{"name": "search_library"}</tool_call>'
    answer, unfinished, discarded = messages[-1]["content"], False, None
    # No answer: a lookup written out as text, or cut off inside one, nothing at all, a tool's error repeated as the
    # answer, or "Let me check one more source." before a lookup it wasn't given.
    no_answer = lambda text: text.lstrip().startswith(TOOL_MARKUP) or not text.strip() \
        or text.strip().strip('"') in TOOL_ERRORS or bool(dropped and LOOKUP_PREAMBLE.match(text.strip()))  # noqa: E731
    if tools and no_answer(answer):
        discarded = answer  # kept for the eval logs
        rescue = yield from _rescue(model, library, messages, question, sources, seen, options)
        if rescue:
            tokens, seconds, cut_off = tokens + rescue["tokens"], seconds + rescue["seconds"], cut_off or rescue["cut_off"]
            if not no_answer(rescue["text"]):
                answer = messages[-1]["content"] = rescue["text"]  # the saved chat keeps the answer it gave
    read = _one_per_article([{"id": k, **v} for k, v in sources.items()])
    found = _one_per_article(read + [{"id": k, **v} for k, v in seen.items()])  # read first, then the rest
    if no_answer(answer):
        answer, unfinished = "", True  # nothing to show
    elif library:
        answer = TOOL_SOURCES.sub("", answer).strip("\n")  # the Sources line added below says what it really read
        # The model names the sources it used, and the screen shows every article it opened. Models still name sources
        # they never opened (evals/citation_check.py), so a Sources line that does is replaced by what it read.
        if read:
            line = "Sources: " + "; ".join(f"{s['title']} ({s['source']})" for s in read[:6])
        elif looked:
            line = "Sources: none opened (it only saw the search results below)"
        elif earlier:
            line = "Sources: what it read earlier in this chat"
        else:
            line = "Sources: none (from its own knowledge)"
        # Articles it only saw in search results count too: they exist, and it saw their excerpts.
        shown, ids = read_before + [{"id": k, **v} for k, v in seen.items()], set(sources) | set(seen)
        by_id = {**seen, **sources}
        made_up = lambda items: [n for n in items or [] if not _opened(n, read, shown, ids)]  # noqa: E731
        # "...add it to the file. Sources: X" at the very end goes on a line of its own, but only when X names what it
        # read or saw: in "Heat one room. Source: a wood stove, never a grill indoors" it is part of the answer.
        moved = INLINE_SOURCES.sub(r"\1\n\n\2", answer)
        if moved != answer and cited_sources(moved) and not made_up(cited_sources(moved)):
            answer = moved
        named = cited_sources(answer)
        unopened = made_up(named)
        # "OK, I'll forget where you live." answers a request, not a question: no "from its own knowledge" line. Only
        # when the message asks nothing else and the reply reads as a short acknowledgment ("Remember my son weighs
        # 16 kg. how much Tylenol can he have" still gets the line).
        just_memory = not named and not read and not looked and not earlier and asked_memory(question) \
            and not INFO_ASK.search(question) and ACKNOWLEDGED.search(answer.replace("’", "'")) and len(answer) < 300
        if (not named or unopened) and not just_memory:
            answer = _with_sources_line(answer, line)
        elif named and any(_known_ids(item, by_id) for item in named):  # named by id, meaningless to the person
            answer = _with_sources_line(answer, "Sources: " + "; ".join(_titled(item, by_id) for item in named))
        # "(ids 1403312, 1400192, etc.)" in the text goes; "(ID 4471203)" from the person's insurance card doesn't.
        block, pool = _sources_block(answer), known | ids | {s["id"] for s in read_before if s.get("id") is not None}
        cut = block[0] if block else len(answer)
        answer = ID_REMARK.sub(lambda m: "" if _known_ids(m.group(0), pool, every=True) else m.group(0), answer[:cut]) \
            + answer[cut:]
    yield {"type": "done", "tokens": tokens, "seconds": seconds, "answer": answer, "cut_off": cut_off,
           "unfinished": unfinished, "unopened": unopened, "named": named if library and not unfinished else None,
           "sources": read, "seen": found[len(read):], "think": think, "discarded": discarded}
    # Only when they said something about themselves or their family, or asked it to remember or forget something: the
    # step takes a few seconds. Not after an answer cut off at the length limit, which "Keep going" continues. It reads
    # only what the person said, so an answer that didn't finish doesn't stop it.
    if memory is not None and memory.ai_writes and not cut_off and _about_them(question, messages, memory):
        try:
            yield from memory_check(model, messages, memory, think_setting(model, caps), options)
        except Exception:  # noqa: BLE001 - the answer is out; a failed memory step only means nothing new was saved
            yield {"type": "memory_failed"}


def _test_case():
    """A case a dev copy forces so it can be tried with a real model (bin/dev --test): "no-answer" (every answer comes
    out as a lookup written as text) or "think-limit=N" (reasoning stops after N tokens). Ignored outside dev copies."""
    case = os.environ.get("SURVIVAL_LLM_TEST", "") if os.environ.get("SURVIVAL_LLM_DEV") else ""
    return case if case == "no-answer" or re.fullmatch(r"think-limit=\d+", case) else ""


def _rescue(model, library, messages, question, sources, seen, options):
    """It looked things up but wrote no answer: show it the best passages its searches found (what it read first, else
    the top search results, else a search for the question) and ask once more, without tools or reasoning. Yields a
    read event for each passage it is given; returns {"text", "tokens", "seconds", "cut_off"}, or None with nothing to
    give it."""
    picks = list(sources) + [pid for pid in seen if pid not in sources]
    picks = picks or [h["id"] for h in library.search(question, limit=4)]
    blocks = []
    for pid in picks:
        doc = library.read(pid, max_chars=2500)
        if not doc:
            continue
        blocks.append(f"[{doc['title']} ({doc['source']})]\n{doc['text']}")
        if pid not in sources:
            sources[pid] = {k: doc[k] for k in ("title", "source", "official")}
            yield {"type": "read", "id": pid, **sources[pid]}
        if len(blocks) == 4:
            break
    if not blocks:
        return None
    yield {"type": "retry", "why": "excerpts"}  # what streamed so far isn't the answer
    messages.append({"role": "user", "content": RESCUE_NOTE + "\n\n" + "\n\n".join(blocks)})
    content, final = [], {}
    try:
        for chunk in _stream(model, messages, None, False, options):
            msg = chunk.get("message", {})
            if msg.get("thinking"):
                yield {"type": "thinking", "text": msg["thinking"]}
            if msg.get("content"):
                content.append(msg["content"])
                yield {"type": "token", "text": msg["content"]}
            elif not msg.get("thinking"):
                yield {"type": "tick"}
            if chunk.get("done"):
                final = chunk
    finally:
        messages.pop()  # the note and its excerpts stay out of the saved conversation
    return {"text": "".join(content), "tokens": final.get("eval_count", 0),
            "seconds": final.get("eval_duration", 0) / 1e9, "cut_off": final.get("done_reason") == "length"}


# The notes in MEMORY_CHECK's examples: Granite once saved the generator-manual example's note for
# someone's EU2200i manual.
EXAMPLE_NOTES = {n.lower() for n in re.findall(r'"(?:remember": \[|new": )"([^"]+)"', MEMORY_CHECK)}
NOT_NAMES = set("How What When Where Why Which Who Whose Can Could Should Would Will Does Did Do The This That These "
                "Those Is Are Was Were Has Have Had Takes Lives Uses Owns Keeps Their They There Please Also And But "
                "Then Actually Okay Yes Our Its Any Some Every".split())


def _about_them(question, messages, memory):
    """Whether the person's message may say something about them worth a note: "my", a family word or a memory
    request, or someone their notes name ("Leo is allergic to peanuts too"), or he/she right after they spoke about
    their family ("Actually he's 9, not 8")."""
    if PERSONAL.search(question) or asked_memory(question):
        return True
    notes = " ".join(memory.notes())
    if any(re.search(rf"\b{w}\b", notes) for w in set(re.findall(r"\b[A-Z][a-z]{2,}\b", question)) - NOT_NAMES):
        return True
    said = [m["content"] for m in messages if m.get("role") == "user"]
    return bool(re.search(r"\b(he|she|him|her|his|hers)\b|\b(he|she)['’]s\b", question, re.I)) \
        and any(PERSONAL.search(m) for m in said[-5:-1])


def memory_check(model, messages, memory, think, options):
    """Let the model save, change or delete notes about the person, from what they just said (and, for context, a
    few of their earlier messages in this chat)."""
    said = [m["content"].split("\n\nLibrary excerpts:", 1)[0]  # models without tools get excerpts added to questions
            for m in messages if m.get("role") == "user"]
    notes = "\n".join(f"- {n}" for n in memory.notes()) or "(none yet)"
    earlier = "".join(f'Earlier in this chat they said: "{m[:300]}"\n' for m in said[-4:-1])
    fill = {"notes": notes, "earlier": earlier + ("\n" if earlier else ""), "said": said[-1] if said else ""}
    prompt = re.sub(r"\{(notes|earlier|said)\}", lambda m: fill[m.group(1)], MEMORY_CHECK)  # one pass: notes may hold braces
    yield {"type": "memory_check"}
    reply = []
    # The same num_ctx as the answer: a different one would make Ollama load the model again.
    for chunk in _stream(model, [{"role": "user", "content": prompt}], None, think,
                         {**options, "num_predict": 600, "temperature": 0.3}):
        reply.append(chunk.get("message", {}).get("content") or "")
        yield {"type": "tick"}
    changed = False
    plan = memory_plan("".join(reply))
    words = _stems(said[-1] if said else "")
    copied = lambda note: note.strip().lower() in EXAMPLE_NOTES and not _stems(note) <= words  # noqa: E731
    asked = lambda note: _is_question(note, said[-1] if said else "")  # noqa: E731
    plan["remember"] = [n for n in plan["remember"] if not copied(n) and not asked(n)]  # not a fact about them
    plan["change"] = [c for c in plan["change"] if not copied(c["new"]) and not asked(c["new"])]
    for event in memory.apply(forgets(plan, said[-1] if said else "", memory.notes())):
        changed = True
        yield event
    if not changed and asked_memory(said[-1] if said else ""):
        yield {"type": "memory_unchanged"}  # they asked it to remember or forget something, and nothing changed


def _is_question(note, said):
    """Whether a note the model wants to keep is the person's question rather than a fact about them: Lightning saved
    "Where can I safely run a generator?" both times it was asked (0.3.1 Windows test)."""
    text, ask = note.strip(" \"'“”‘’"), said.strip(" \"'“”‘’")
    return text.endswith("?") or (ask.endswith("?") and _stems(text) == _stems(ask))


def memory_plan(reply):
    """The model's JSON reply as {"forget": [...], "change": [{"old", "new"}], "remember": [...]}; empty if unreadable.
    Takes the first JSON object in the reply that has any of those keys, and a single item where a list belongs."""
    plan, decoder = {}, json.JSONDecoder()
    # Small slips that make the rest unreadable: a stray quote before the closing brace, a comma before it.
    reply = reply + "\n" + re.sub(r",\s*([}\]])", r"\1", re.sub(r'(\])\s*"\s*(\})', r"\1\2", reply))
    for i, ch in enumerate(reply):
        if ch != "{":
            continue
        try:
            found = decoder.raw_decode(reply, i)[0]
        except ValueError:
            continue
        if isinstance(found, dict) and {"forget", "change", "remember"} & set(found):
            plan = found
            break

    def items(key):
        value = plan.get(key)
        return value if isinstance(value, list) else [value] if isinstance(value, (str, dict)) else []

    texts = lambda key: [x for x in items(key) if isinstance(x, str) and x.strip()]  # noqa: E731
    return {"forget": texts("forget"), "remember": texts("remember"),
            "change": [c for c in items("change") if isinstance(c, dict)
                       and isinstance(c.get("old"), str) and isinstance(c.get("new"), str)]}


def _sources_block(answer):
    """The answer's closing list of sources as (start, end, items), or None. That is the last "Sources" line or heading,
    with any list right under it and at most a short remark after; a lone "Source:" line counts only as the very last
    line, since one higher up may be part of the answer ("Source: rain barrel")."""
    found = list(SOURCES_LINE.finditer(answer))
    if not found:
        return None
    line = found[-1]
    plural = bool(re.match(r"^[*_# ]*Sources", line.group(0), re.IGNORECASE))
    head = re.sub(r"^[*_# ]*Sources?[*_ ]*:?", "", line.group(0), flags=re.IGNORECASE)
    items, end = [p.strip(" *_.") for p in _split_outside_brackets(head)], line.end()
    if plural:
        bare = not [i for i in items if i]  # "Sources:" alone: the rows right under it are its list, bulleted or not
        for row in answer[end:].split("\n")[1:]:
            if LIST_ITEM.match(row):
                items.append(row[LIST_ITEM.match(row).end():].strip(" *_."))
            elif ID_ROW.match(row):  # "[id 1403312] Water storage (Ready.gov)", the way search results list them
                items.append(row.strip(" *_."))
            elif bare and row.strip() and not row.lstrip().startswith("|") \
                    and ("(" in row or not row.rstrip(" *_").endswith((".", "!", "?"))):  # a sentence is the answer's
                items += [p.strip(" *_.") for p in _split_outside_brackets(row)]
            elif row.strip():
                break
            elif bare and any(items):
                break  # a blank line ends a list without bullets
            end = min(len(answer), end + 1 + len(row))
    tail = answer[end:].strip()
    if (tail and not plural) or len(tail) > 300:
        return None
    return line.start(), end, [item for item in items if item]


def cited_sources(answer):
    """What the answer's closing Sources line names, item by item; None if it has none."""
    block = _sources_block(answer)
    return block[2] if block else None


def _split_outside_brackets(text, separators=(";", " | ")):
    """Split text at the separators, but not inside parentheses or brackets."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(text):
        depth += text[i] in "([" and 1 or text[i] in ")]" and -1 or 0
        sep = next((x for x in separators if depth <= 0 and text.startswith(x, i)), None)
        if sep:
            parts.append(text[start:i])
            start = i = i + len(sep)
            continue
        i += 1
    return parts + [text[start:]]


GENERIC = STOPWORDS | set("manual manuals guide guides guideline guidelines guidance article articles page pages "
                          "section chapter book document entry entries website site library offline pdf via id "
                          "information info recommendation recommendations".split())


def _content_words(text):
    return {w for w in re.findall(r"[a-z0-9]+", re.sub(r"\bid\s*\d+", " ", text.lower())) if w not in GENERIC}


TRAILING_PARENS = re.compile(r"^(.*?)\s*\(((?:[^()]|\([^()]*\))*)\)\s*$")


PUBLISHERS = re.compile(r"\b(mayo|webmd|healthline|cleveland clinic|johns hopkins|harvard|red cross|aap|fda|epa|osha|"
                        r"noaa|usda|nhs|cdc|nih|fema|ready\.?gov|medlineplus|wikem|wikimed|wikipedia|wikihow|ifixit|"
                        r"stack exchange|appropedia|energypedia|ifrc|your files)\b", re.IGNORECASE)


def _claims_source(paren, articles):
    """Whether words in parentheses name who published a source ("Mayo Clinic", "Ready.gov", a library collection)
    rather than describe it ("FEMA's advice on bleach" is caught too; "Emergency Visual Signals" isn't)."""
    words = _content_words(paren)
    return bool(words) and (bool(PUBLISHERS.search(paren) or re.search(r"\bWHO\b", paren))
                            or any(words <= _content_words(a["source"]) for a in articles))


def _names_article(text, article, articles, full=None):
    """Whether one named source is this article: (nearly) its whole title or a shortened form of it, or just its
    collection's name. A publisher in parentheses at the end of the full item must be the article's own."""
    title, source = _content_words(article["title"]), _content_words(article["source"])
    found = TRAILING_PARENS.match(full or text)
    if found and _claims_source(found.group(2), articles) and not _content_words(found.group(2)) <= title | source:
        return False  # "Fever (Mayo Clinic)" when it read MedlinePlus
    found = TRAILING_PARENS.match(text)
    words = _content_words(found.group(1) if found else text)
    if not words:
        return bool(found)
    allowed = 1 if len(title) > 2 else 0  # a short title fits inside many made-up ones ("Fever in Children")
    if title and len(title & words) >= max(1, 0.8 * len(title)) and len(words - title - source) <= allowed:
        return True
    if title and len(words - source) >= 2 and words - source <= title:  # a shortened title
        return True
    return words <= source  # just the collection: fine if it read something from it


def _opened(item, read, read_before=(), opened_ids=()):
    """Whether a source the model named is one it opened: by passage id, by title or by its collection's name.
    Models describe a source after a dash or colon; a list of several in one item must check out one by one."""
    if re.match(r"none\b", item.strip(" *_\"'“”‘’").lower()):  # saying it used none is never a made-up source
        return True
    ids = [int(n) for n in re.findall(r"\b\d{5,}\b", item)]
    if ids and all(i in opened_ids for i in ids):
        return True
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", item)  # a Markdown link: its text, not its address
    text = re.sub(r"https?://\S+", " ", text).strip(" *_.\"'“”‘’")
    articles = list(read) + list(read_before)
    collections = [_content_words(a["source"]) for a in articles]
    # "WikEM: ACE inhibitor dose table": before the colon or dash is just a collection's name, so what comes after
    # names the article, and has to be one it opened (a made-up title passed the check in the 0.3.0 Windows test).
    collection_only = lambda head: bool(_content_words(head)) and any(_content_words(head) <= c for c in collections)  # noqa: E731
    variants = [(text, text)]  # (what names the source, the text whose closing parentheses must fit)
    variants += [(text.split(sep, 1)[0],) * 2 for sep in (" – ", " — ", " - ")  # after a dash: a description
                 if sep in text and not collection_only(text.split(sep, 1)[0])]
    if ": " in text and not collection_only(text.split(": ", 1)[0]):  # a colon may be part of the title, so the
        variants.append((text.split(": ", 1)[0], text))                 # full item's parentheses still count
    if any(_names_article(v.strip(" \"'“”‘’"), a, articles, full) for v, full in variants for a in articles):
        return True
    parts = [p for p in _split_outside_brackets(text, (", ", " and ", " & ")) if p.strip()]
    return len(parts) > 1 and all(_opened(p, read, read_before, opened_ids) for p in parts)


def _read_earlier(messages):
    """Articles opened for earlier questions in this chat ({title, source}), from the tool results kept in it."""
    found = []
    for m in messages:
        if m.get("role") == "tool" and m.get("tool_name") == "read_article":
            first = (m.get("content") or "").split("\n", 1)[0]
            parsed = re.match(r"^(.*) \(((?:[^()]|\([^()]*\))*)\)$", first)
            if parsed:
                found.append({"title": parsed.group(1), "source": parsed.group(2)})
    return found


# A message that asks for information as well as "remember this", and a reply that only acknowledges a memory request.
INFO_ASK = re.compile(r"\?|\b(how (much|many|long|often|do|does|can|should)|what|which|tell me|explain|is it safe|safe "
                      r"to|can (i|he|she|we|they|you)|should (i|he|she|we|they)|doses?|dosage)\b", re.I)
ACKNOWLEDGED = re.compile(r"\b(i'll remember|i will remember|i've noted|noted|got it|i'll keep|i've saved|saved|"
                          r"i've forgotten|forgotten|i'll forget|deleted|removed|no longer|won't remember)\b", re.I)


def _with_sources_line(answer, line):
    """The answer with its closing Sources block (the line and any list right under it) replaced by line, or with
    line added at the end when it has none."""
    block = _sources_block(answer)
    if not block:
        return f"{answer.rstrip()}\n\n{line}"
    after = answer[block[1]:].strip()
    return f"{answer[:block[0]].rstrip()}\n\n{line}" + (f"\n\n{after}" if after else "")


def _known_ids(text, known, every=False):
    """The passage ids text names that are in known (with every: [] unless all its numbers are)."""
    found = [int(n) for n in re.findall(r"\b\d{5,}\b", text) if len(n) < 19]
    hits = [n for n in found if n in known]
    return hits if hits and (not every or len(hits) == len(found)) else []


def _titled(item, by_id):
    """A Sources item that names passages by id, in words: the ids go, and if nothing else is left, the titles of those
    passages take their place ("1403312 (Ready.gov)" becomes "Generator Safety (Ready.gov)"). Numbers that aren't
    passage ids ("Champion 100891 Owner's Manual") stay."""
    passages = []

    def drop(m):
        hits = _known_ids(m.group(0), by_id, every=True)
        passages.extend(by_id[n] for n in hits)
        return " " if hits else m.group(0)

    rest = ID_REF.sub(drop, item)
    for _ in range(2):
        rest = re.sub(r"[(\[][\s,;:*_]*[)\]]", "", rest)  # brackets left empty
        rest = re.sub(r"[\s,;:]+(?=[)\]])|(?<=[(\[])[\s,;:]+", "", rest)  # "(Ready.gov, )"
    rest = re.sub(r"\s{2,}", " ", rest).strip(" ,;:–—-*_#")
    if re.sub(r"\([^)]*\)", "", rest).strip(" ,;:–—-\"'“”*_#"):  # it still names the article itself
        return rest
    named = _one_per_article([p for p in passages if p.get("title")])
    return "; ".join(f"{p['title']} ({p['source']})" for p in named) or rest


def _one_per_article(items):
    """Several passages of one article share its title; list each article once, at its first passage."""
    out, keys = [], set()
    for item in items:
        if (item["title"], item["source"]) not in keys:
            keys.add((item["title"], item["source"]))
            out.append(item)
    return out


def trim(messages, budget=60000):
    """Blank out old tool results so long chats stay inside the context window."""
    total = sum(len(m.get("content") or "") for m in messages)
    for m in messages[1:-6]:
        if total <= budget:
            break
        # A tool's error stays: it is short, and trimmed it would look like a result (_used_ids).
        if m["role"] == "tool" and m["content"] not in TOOL_ERRORS \
                and not m["content"].endswith("[old result removed]"):
            total -= len(m["content"])
            title = m["content"].split("\n", 1)[0] if m.get("tool_name") == "read_article" else ""
            m["content"] = f"{title}\n[old result removed]" if title else "[old result removed]"  # keeps what it read


def installed_models():
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=5) as resp:
            return [m["name"] for m in json.load(resp).get("models", [])]
    except OSError:
        return None  # Ollama is not running
