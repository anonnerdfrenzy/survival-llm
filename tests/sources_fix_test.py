"""Checks for two small fixes from the 0.3.0 Windows test (done Oct 28 2026):
a made-up title after a real collection's name ("WikEM: ACE inhibitor dose table") must not pass the Sources check,
and a reply that only answers "remember this" or "forget that" gets no "Sources: none (from its own knowledge)" line.
No Ollama: a fake model (core._stream) and a fake library.

Usage: .venv/bin/python tests/sources_fix_test.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


# ---- a made-up title after a collection's name ----
read = [{"title": "Hypertension", "source": "WikEM"}]
for item, want in [("WikEM: ACE inhibitor dose table", False), ("WikEM - ACE inhibitor dose table", False),
                   ("WikEM — ACE inhibitor dose table", False), ("ACE inhibitor dose table (WikEM)", False),
                   ("WikEM", True), ("WikEM: Hypertension", True), ("Hypertension (WikEM)", True),
                   ("Hypertension: first-line treatment", True), ("Hypertension - what to start with", True)]:
    check(f"_opened({item!r}) == {want}", core._opened(item, read) == want, core._opened(item, read))

# ---- replies to "remember" and "forget" ----
rounds = []


def fake_stream(model, messages, tools, think, options):
    yield from rounds.pop(0)
    yield {"done": True, "eval_count": 1, "eval_duration": 1}


core._stream = fake_stream


class Lib:
    has_personal = False

    def labels(self):
        return ["Ready.gov"]

    def search(self, query, topic="any", limit=8):
        return []

    def read(self, pid, max_chars=5000):
        return None


def answer(question, reply):
    rounds[:] = [[{"message": {"content": reply}}]]
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": question}]
    return next(e for e in core.chat_events("nemotron", Lib(), msgs, caps={"tools"}) if e["type"] == "done")["answer"]


got = answer("Please forget where I live.", "Done. I've forgotten where you live.")
check("forget: no Sources line", "Sources" not in got, got)
got = answer("Remember that my son Leo has type 1 diabetes.", "Got it. I'll remember that Leo has type 1 diabetes.")
check("remember: no Sources line", "Sources" not in got, got)
got = answer("Remember I'm on blood thinners. Can I take ibuprofen for my back?",
             "Ibuprofen raises bleeding risk with blood thinners; ask your doctor first and consider acetaminophen.")
check("remember plus a question: still says it answered from its own knowledge",
      "Sources: none (from its own knowledge)" in got, got)
got = answer("Remember my son is 4 and weighs 16 kg. how much childrens tylenol can he have",
             "Got it. For 16 kg, the usual dose is 240 mg every 4 to 6 hours; check the package.")
check("remember plus a dosing question without a question mark: keeps the line (review, Oct 28)",
      "Sources: none (from its own knowledge)" in got, got)
got = answer("Keep in mind I'm pregnant. Tell me which painkillers are safe.",
             "Noted. Acetaminophen is generally considered the safest choice in pregnancy; avoid ibuprofen.")
check("keep in mind plus 'tell me which': keeps the line", "Sources: none (from its own knowledge)" in got, got)
got = answer("Remember that I can't eat gluten.", "Got it, I’ll remember that you can't eat gluten.")
check("remember with a curly apostrophe in the reply: no line", "Sources" not in got, got)
got = answer("How long is fridge food safe in a blackout?", "About 4 hours if you keep the door closed.")
check("a plain question answered from memory keeps the line", "Sources: none (from its own knowledge)" in got, got)

print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all passed'}")
sys.exit(1 if FAILS else 0)
