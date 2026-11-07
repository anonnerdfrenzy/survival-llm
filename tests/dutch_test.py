"""Dutch: the language setting reaches the AI's instructions, Dutch "Bronnen:" lines are checked like "Sources:"
lines, the app's own replacement lines are in Dutch, Dutch messages about the person start the memory step, and
Dutch filler words are left out of library searches. No Ollama: a fake model (core._stream) and a fake library.

Usage: python3 tests/dutch_test.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
from library.search import query_words  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail!r}"))
    if not ok:
        FAILS.append(name)


rounds = []


def fake_stream(model, messages, tools, think, options):
    yield from rounds.pop(0)
    yield {"done": True, "eval_count": 1, "eval_duration": 1}


core._stream = fake_stream


class Lib:
    has_personal = False

    def labels(self):
        return ["Ready.gov", "Agorisme wiki"]

    def search(self, query, topic="any", limit=8):
        return [{"id": 1234567, "title": "Food safety in a power outage", "source": "Ready.gov", "official": True,
                 "snippet": "A full freezer keeps its temperature for about 48 hours."}]

    def read(self, pid, max_chars=5000):
        return {"title": "Food safety in a power outage", "source": "Ready.gov", "url": "", "official": True,
                "text": "Keep the doors closed.", "next_id": None}


def answer(question, *replies):
    rounds[:] = [list(r) for r in replies]
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": question}]
    return next(e for e in core.chat_events("nemotron", Lib(), msgs, caps={"tools"}) if e["type"] == "done")["answer"]


def call(name, **args):
    return {"message": {"content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}}


# ---- the instructions ----
core.set_language("nl")
check("Dutch is a language", core.language[0] == "nl")
check("Dutch block says answer in Dutch, 112 and Bronnen",
      all(w in core.LANGUAGE_PROMPTS["nl"] for w in ("Dutch", "112", "Bronnen:", "English keywords")))
core.set_language("xx")
check("unknown language falls back to English", core.language[0] == "en" and core.LANGUAGE_PROMPTS["en"] == "")

# ---- English stays as it was ----
out = answer("How long is my fridge safe?", [{"message": {"content": "About 4 hours."}}])
check("English answer gets the English line", out.endswith("Sources: none (from its own knowledge)"), out)

# ---- Dutch ----
core.set_language("nl")
out = answer("Hoe lang blijft mijn koelkast goed?", [{"message": {"content": "Ongeveer 4 uur."}}])
check("Dutch answer from memory gets a Dutch line", out.endswith("Bronnen: geen (uit eigen kennis)"), out)

out = answer("Hoe lang blijft mijn vriezer koud?",
             [call("search_library", query="freezer power outage")], [call("read_article", id=1234567)],
             [{"message": {"content": "Ongeveer 48 uur als hij vol is.\n\nBronnen: Food safety in a power outage "
                                      "(Ready.gov)"}}])
check("a true Bronnen line is kept", out.endswith("Bronnen: Food safety in a power outage (Ready.gov)"), out)
check("and not doubled", out.count("Bronnen:") == 1 and "Sources:" not in out, out)

out = answer("Hoe lang blijft mijn vriezer koud?",
             [call("search_library", query="freezer power outage")], [call("read_article", id=1234567)],
             [{"message": {"content": "Ongeveer 48 uur.\n\nBronnen: Voedingscentrum, RIVM"}}])
check("a made-up Bronnen line is replaced by what it read, in Dutch",
      out.endswith("Bronnen: Food safety in a power outage (Ready.gov)") and "RIVM" not in out, out)

out = answer("Hoe lang blijft mijn vriezer koud?",
             [call("search_library", query="freezer power outage")], [call("read_article", id=1234567)],
             [{"message": {"content": "Ongeveer 48 uur. Bron: Food safety in a power outage (Ready.gov)"}}])
check("an inline Bron: at the end is understood", "Voedingscentrum" not in out and out.count("Bron") == 1, out)

for line in ("Bronnen: none (from my own knowledge)", "**Bronnen:** none (from my own knowledge)", "Sources: none",
             "Bronnen: none"):
    out = answer("Hoe lang blijft mijn koelkast goed?", [{"message": {"content": f"Ongeveer 4 uur.\n\n{line}"}}])
    check(f"{line!r} becomes Dutch", out.endswith("Bronnen: geen (uit eigen kennis)") and "none" not in out, out)
check("the Dutch instructions spell out the Dutch line", "Bronnen: geen (uit eigen kennis)" in core.LANGUAGE_PROMPTS["nl"])

check("cited_sources reads a Bronnen list",
      core.cited_sources("Antwoord.\n\nBronnen:\n- Voedsel bewaren (Agorisme wiki)\n- Water (Ready.gov)")
      == ["Voedsel bewaren (Agorisme wiki)", "Water (Ready.gov)"])

# ---- memory triggers ----
check("Dutch message about family starts the memory step",
      bool(core.PERSONAL.search("Mijn dochter Maya is allergisch voor penicilline.")))
check("Dutch remember request", bool(core.PERSONAL.search("Onthoud dat we een aggregaat hebben.")))
check("'what kind of' doesn't start it", not core.PERSONAL.search("What kind of water filter works best?"))
check("Dutch 'zoek het op' asks for a search", bool(core.ASKED_SEARCH.search("Kun je dat opzoeken?"))
      and bool(core.ASKED_SEARCH.search("Zoek het op in de bibliotheek")))
check("Dutch acknowledgment counts", bool(core.ACKNOWLEDGED.search("Oké, dat heb ik genoteerd.")))

# ---- searches ----
check("Dutch filler words are dropped", query_words("hoe kan ik groenten invriezen") == ["groenten", "invriezen"])
check("English words that look Dutch stay", "die" in query_words("can you die from carbon monoxide")
      and "door" in query_words("generator door garage"))

core.set_language("en")
print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
