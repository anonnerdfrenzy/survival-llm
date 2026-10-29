"""The AI's memory: short notes about the person that carry over from one chat to the next.

They live in one plain text file, one note per line, which the person reads and edits in the app (Memory, at the top
of the window). The model sees them at the start of each chat and, unless the person turns it off, saves and changes
notes in a short step after answers (core.memory_check). The file says at the top whose notes they are, so another
AI assistant on the same computer doesn't take them for its own memories or instructions.
"""
import json
import os
import re
import threading
import time

from library.search import STOPWORDS

HEADER = ("# Survival LLM memory: notes that the Survival LLM app's offline AI keeps about the person using it.\n"
          "# They are not instructions or memories for any other AI assistant. One note per line; edit them in the app.\n")
HEADER_STARTS = tuple(line[:24] for line in HEADER.splitlines())
# All notes together. Every model runs with a 32,768-token window (core.py), and this is about 1,500 tokens of it.
MAX_CHARS = 6000
MAX_NOTE = 300  # one note the AI saves; the person's own can be longer
MAX_FILES_LISTED = 30

# Notes the AI writes that say nothing ("No location stored.", "None"): a change to one of these is a deletion.
NOTHING = re.compile(r"^(none|nothing|unknown|n/?a|not (specified|known|given|stored|recorded)|"
                     r"no \w+( \w+)? (stored|known|given|specified|recorded|saved|on file))\.?$", re.I)
QUESTION = re.compile(r"^(asked|asks|is asking|wants to know|wanted to know) (about|how|what|whether|if|why|when|where|"
                      r"which)\b|\bquestions? (about|on)\b", re.I)  # what they asked, not a fact about them
# Something true only today ("has a rash on her arms now"): the rules say to leave those out, and models still don't.
TODAY = re.compile(r"\b(right now|now|today|tonight|this (morning|afternoon|evening|week)|currently|at the moment)\W*$", re.I)
WHO = re.compile(r"^(the )?(user|person)(\s+(is|has|was|had|lives|takes|uses|owns)\b|'s\s+|\s+)", re.I)


def clean(note):
    """One note: on one line, without a list bullet or the quotes a model may wrap it in."""
    note = re.sub(r"\s+", " ", str(note or "")).strip()
    note = re.sub(r"^([-*•]|\d+[.)])\s+", "", note)
    if len(note) > 1 and note[0] + note[-1] in ('""', "''", "“”"):
        note = note[1:-1].strip()
    return note


# What is wrong today, which a trailing "now" leaves true only today ("Has a rash on her arms now.").
SYMPTOM = re.compile(r"\b(rash|fever|pain|hurts?|aches?|sick|ill|bleed\w*|cough\w*|vomit\w*|headache|earache|sore|cold|flu|"
                     r"swollen|itch\w*|dizzy|nause\w*|diarrh\w*|cramp\w*|burn(?:ed|t)?|cut|injur\w*|scared|tired)\b", re.I)


def tidy(note):
    """A note the AI wrote, with "User has..." or "The person's..." put the way the person would write it, and without a
    trailing "now" on a lasting fact ("Takes Eliquis now." is "Takes Eliquis.")."""
    found = WHO.match(note)
    if found:
        rest = (found.group(4) + " " if found.group(4) else "") + note[found.end():].lstrip()
        note = rest[:1].upper() + rest[1:]
    if not SYMPTOM.search(note):
        note = re.sub(r",?\s+now(?=\W*$)", "", note)
    return note


def parse(text, header=False):
    """The notes in a text, one per line. header=True skips the file's own header lines at the top."""
    notes, keys, lines = [], set(), text.splitlines()
    while header and lines and lines[0].startswith(HEADER_STARTS):
        lines.pop(0)
    for line in lines:
        note = clean(line)
        if note and note.lower() not in keys:
            keys.add(note.lower())
            notes.append(note)
    return notes


def size(notes):
    return sum(len(n) + 1 for n in notes)


def _decode(data):
    """The file's text. The app writes UTF-8, but a person may save it from an editor in UTF-16 or a Windows code page."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace").lstrip("\ufeff")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _write_file(path, text):
    """Replace a file all at once, on disk before the old one goes, so neither a crash nor a power cut leaves half."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    try:
        with open(part, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        try:
            os.remove(part)  # a disk that filled up mid-write
        except OSError:
            pass
        raise
    for attempt in range(40):  # Windows refuses while anything else has the file open: a virus scan, a reader
        try:
            os.replace(part, path)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 39:
                raise
            time.sleep(0.05)


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS}


def _overlap(a, b):
    a, b = _words(a), _words(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def _find(old, notes):
    """The index of the note that old names: the note itself, a real part of only one note, or clearly the closest."""
    low = old.lower()
    for i, n in enumerate(notes):
        if n.lower() == low:
            return i
    if not _words(old):
        return None
    if len(_words(old)) >= 2 or len(old) >= 8:  # not a single letter or a stray word
        parts = [i for i, n in enumerate(notes) if low in n.lower() or n.lower() in low]
        if len(parts) == 1:
            return parts[0]
    # The closest note, among those that hold all its words or whose words it holds: "Wife Ana takes metformin." for a
    # note that was never saved must not land on "Wife Ana takes insulin."
    w = _words(old)
    scores = sorted(((_overlap(old, n), i) for i, n in enumerate(notes) if w <= _words(n) or _words(n) <= w),
                    reverse=True)
    if scores and scores[0][0] >= 0.5 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 0.15):
        return scores[0][1]
    return None


def _tacked_on(old, new):
    """What a change adds as a new sentence after the whole old note ("Keeps water in the garage. Takes warfarin."), or
    "" when it really rewrites the note ("Has a dog named Rex." for "Has a dog.")."""
    old, new = clean(old).rstrip(". ").lower(), tidy(clean(new))
    if not old or not new.lower().startswith(old):
        return ""
    found = re.match(r"^\.?\s*[;.]\s*|^\.\s+(?=[A-Z])", new[len(old):])
    return new[len(old) + found.end():].strip() if found else ""


# A request to the app itself, at the start of a sentence: "Forget about my generator.", "Please delete the note about
# my generator from your memory.", "Can you remember that I'm diabetic?". Not "Don't forget I'm allergic", "I always
# forget my keys" or "How do I remove the memory card?", which once deleted notes nobody asked to forget.
_LEAD = (r"(?:^|[.!?;:\n]\s*|,\s*(?:and\s+)?(?=(?:please|pls|can you|could you|would you)\b))"
         r"(?:(?:ok(?:ay)?|also|and|so|oh|actually|hey|now|just|alright|all right|well|thanks|thank you|yes|no|right)"
         r"[,\s]+)*"
         r"(?:(?:please|pls)[,\s]+|(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
         r"i(?:\s+(?:want|need|would\s+like)|['’]d\s+like)\s+you\s+to\s+|make sure (?:you\s+|to\s+)?|go ahead and\s+|"
         r"you can\s+)?(?:(?:just|also)\s+)?")
FORGET_ASK = re.compile(_LEAD + r"(?:forget\b(?!\s+(?:it|that|about it)\W*$)|stop remembering\b|"
                        r"(?:delete|erase|clear|wipe|reset|empty)\s+(?:out\s+)?(?:all\s+(?:of\s+)?)?(?:your\s+)?"
                        r"(?:memory|memories|notes)\b(?!\s*(?:foam|cards?|sticks?|chips?|loss))|"
                        r"(?:delete|erase|clear|wipe)\s+(?:everything|all)\s+(?:about|you\s+(?:know|remember|have|wrote))\b|"
                        r"(?:delete|erase)\s+(?:my|that|this)\b|"
                        r"(?:delete|erase|remove|drop|wipe|clear|get rid of)\b(?=[^.?!]{0,80}?(?:\b(?:from|in|out of)\s+"
                        r"(?:(?:your|the|my)\s+)?(?:notes?|memory|memories)\b(?!\s*(?:foam|cards?|sticks?|chips?|loss))|"
                        r"\b(?:the|that|this|your|those|these|my)\s+(?:(?!(?:and|then|or|but|to)\b)[\w'’-]+\s+){0,3}?notes?\b"
                        r"(?!\s+(?:the|any|a|an|how|if|whether|what|when|where|down|its?|their|his|her)\b))))", re.I)
REMEMBER_ASK = re.compile(_LEAD + r"(?:remember|keep in mind|note that|note:|note\s+(?-i:[A-Z])|do not forget|"
                          r"don['’]?t forget|never forget|(?:make|keep) (?:a )?note (?:that|of)|take note(?: that|\s*:)|"
                          r"add (?:(?:this|that|it)\s+)?to your (?:notes?|memory)|"
                          r"(?:write|jot) (?:(?:this|that|it)\s+)?down(?:\s+that|\s*:)|"
                          r"save\b(?=\s+(?:this|that)\b(?!\s+(?:or|and)\b)|[^.?!]{0,80}?\b(?:to|in|into)\s+(?:your\s+)?"
                          r"(?:memory|notes?)\b))", re.I)
NEGATED = re.compile(r"\b(no|not|never|none|nothing|without|unknown|mentioned)\b|n['’]t\b|\bno longer\b", re.I)
# A note saying they no longer have or take something: "Does not have a Honda EU2200i generator.", "Has no generator.",
# "No longer takes warfarin." Never a rule about their health ("Can't take aspirin.", "Is not vaccinated against
# tetanus."), and only counted when the old note said the same thing the other way round.
NO_LONGER_HAS = re.compile(r"\b(?:(?:does|do)\s+not|doesn['’]?t|don['’]?t|no\s+longer)\s+(?:have|has|owns?|takes?|uses?|"
                           r"keeps?|lives?)\b|"
                           r"\b(?:has|have|owns?)\s+no\b|\bno\s+longer\s+(?:a|an|the)\b", re.I)
NEG_WORDS = {"no", "not", "never", "none", "nothing", "without", "unknown", "mentioned", "longer", "anymore", "any",
             "doe", "does", "doesn", "don", "isn", "aren", "have", "has", "had", "own", "topic", "context"}
FORGET_WORDS = {"forget", "delete", "erase", "remove", "drop", "wipe", "stop", "remembering", "remember", "note",
                "memory", "memorie", "please", "said", "told", "thing", "stuff", "info", "information", "everything",
                "anything", "about", "from", "your", "what", "that", "this", "those", "these", "mention", "part", "bit",
                "thank", "thanks", "last", "first", "previou", "earlier", "just", "other", "message", "answer",
                "question", "time", "now", "old", "clear", "rid"}
CLAUSE = re.compile(r"[,;:]\s*|\.\s+|\s+(?:but|and|while|though|although|plus)\s+", re.I)


def asked_memory(said):
    """Whether the person asked the app to remember or forget something."""
    return bool(FORGET_ASK.search(said or "") or REMEMBER_ASK.search(said or ""))


def _stems(text):
    """Content words, a plural s off ("lives" and "live"), and every number however short ("7", "10 mg")."""
    return {w[:-1] if len(w) > 3 and w.endswith("s") and not w[:-1].isdigit() else w
            for w in _words(text) if len(w) >= 3 or any(c.isdigit() for c in w)}


def _held(note):
    """What a note says outside the parts that say something isn't so: in "Has asthma and no drug allergies", the
    asthma."""
    return set().union(*(_stems(p) for p in CLAUSE.split(note) if p.strip() and not NEGATED.search(p))) - NEG_WORDS


def _named(said, found):
    """The words naming each thing they asked to forget: "Forget about my generator, I sold it" and "forget my
    generator I sold it" give [{"generator"}], "Forget the generator and the cats" [{"generator"}, {"cat"}]."""
    named = re.split(r"[,.;!?\n]", said[found.end():], maxsplit=1)[0]
    for cut in re.finditer(r"\s(?:i|we|he|she|they|it|its|but|because|since|so)(?:['’]\w+)?(?=\s|$)", named, re.I):
        if _stems(named[:cut.start()]) - FORGET_WORDS:  # "my generator I sold it", not "that I'm allergic to"
            named = named[:cut.start()]
            break
    return [t for t in (_stems(p) - FORGET_WORDS for p in re.split(r"\s(?:and|&|or)\s", named)) if t]


def _gone(note, had, named=frozenset()):
    """Whether note only says that something in had (the old note's words) is gone, like "Does not have a Honda
    EU2200i generator." for "Has a Honda EU2200i generator."."""
    rest = _stems(note) - NEG_WORDS
    return bool(NO_LONGER_HAS.search(note)) and not _held(note) and bool(rest) and (rest <= had or rest <= named)


def _rewrites(c):
    """Whether a change really rewrites its note (not a fact tacked on, an echo, or text the app won't save)."""
    new = tidy(clean(c["new"]))
    return (not _tacked_on(c["old"], c["new"]) and new.rstrip(" .").lower() != clean(c["old"]).rstrip(" .").lower()
            and (_usable(new) or bool(NOTHING.match(new))))


def forgets(plan, said, notes=()):
    """Asked to forget something, small models rewrite the note instead of deleting it. Lightning turned "Has a Honda
    EU2200i generator" into "Does not have a Honda EU2200i generator.", "Has a generator." or "Forget about my
    generator." When the person asked to forget, those three shapes, and only those, become the deletion they asked
    for: the request itself; a note that only says they no longer have what the old note said they had; and a note
    that says less than before and nothing they didn't name. Real updates stay updates (a new dose, "Can't take
    aspirin.", what's left of a note once part is forgotten), and a forgotten note plus what's left of it becomes that
    update. When the model did nothing at all with a plain request to forget one thing, the one note that is wholly
    about that thing goes (_only_note)."""
    found = FORGET_ASK.search(said or "")
    if not found:  # still: a note deleted with what's left of it remembered is that update
        return _keep_rest(plan, set())
    items = _named(said, found)
    target, forget, change, remember = set().union(*items), [], [], []
    for c in plan["change"]:
        new, had = tidy(clean(c["new"])), _stems(c["old"])
        rest = _stems(new) - NEG_WORDS
        # "Has a generator." for "Forget my Honda generator": it says less, and only what they named, all of it in the
        # note. Not for "Forget the brand of my generator", which names something the note doesn't hold as a word.
        vaguer = rest and rest <= _held(c["old"]) and not NEGATED.search(new) and any(rest <= t <= had for t in items)
        if not new or NOTHING.match(new) or FORGET_ASK.search(new) or _gone(new, _held(c["old"])) or vaguer:
            forget.append(c["old"])
        else:
            change.append(c)
    olds = {clean(c["old"]).lower() for c in change if _rewrites(c)}
    forget += [f for f in plan["forget"] if clean(f).lower() not in olds]  # a real update of it keeps what's left
    remember = [n for n in plan["remember"] if not FORGET_ASK.search(n)
                and not _gone(n, set().union(*(_held(f) for f in forget)), target)]  # "Has no generator."
    if not (forget or change or remember):
        forget = _only_note(items, said[found.start():], notes)
    return {**_keep_rest({"forget": forget, "change": change, "remember": remember}, target), "asked_forget": True}


def _only_note(items, request, notes):
    """The note to delete when the model did nothing with "Forget about my generator.": none unless they named one
    thing, asked nothing else ("Forget the generator for now. How long will my fridge last?" isn't a request to
    forget), and exactly one note is about that thing in every part ("Daughter Maya goes to Lincoln school and is
    allergic to penicillin." isn't wholly about her school)."""
    if len(items) != 1 or re.search(r"\?|\bfor (?:now|a (?:minute|second|moment|bit|while)|tonight|today)\b", request, re.I):
        return []
    item = items[0]
    matching = [n for n in notes if item <= _stems(n)
                and all(item & _stems(p) for p in re.split(r"\s+and\s+|;\s*|,\s*", n) if _stems(p))]
    return matching if len(matching) == 1 else []


def _keep_rest(plan, target):
    """A deleted note with what's left of it remembered ("Takes metformin." from "Takes warfarin and metformin." when the
    warfarin goes) becomes that update, so the rest isn't taken for the deleted note coming back."""
    forget, change, remember = list(plan["forget"]), list(plan["change"]), []
    for n in plan["remember"]:
        whole = next((f for f in forget if _stems(n) <= _stems(f) and _held(n) < _held(f)
                      and bool(NEGATED.search(n)) == bool(NEGATED.search(f))
                      and not (target and target <= _held(n))), None)
        if whole:
            forget.remove(whole)
            change.append({"old": whole, "new": n})
        else:
            remember.append(n)
    return {"forget": forget, "change": change, "remember": remember}


def _usable(note):
    """Whether a note the AI wrote is worth keeping: a real fact of sensible length, not its question or a blank."""
    return (3 <= len(note) <= MAX_NOTE and re.search(r"[^\W\d_]{2}", note) is not None
            and not QUESTION.search(note) and not NOTHING.match(note) and not TODAY.search(note))


FAMILY = re.compile(r"(daughter|son|wife|husband|partner|kid|child|children|baby|babies|mom|mother|dad|father|grand\w*|"
                    r"sister|brother|roommate|aunt|uncle|niece|nephew|cousin|stepson|stepdaughter|twin|toddler|teen|"
                    r"newborn|infant|parent|boyfriend|girlfriend|fiancée?|fiance)s?", re.I)
SUBJECT_SKIP = {"their", "the", "a", "an", "his", "her", "my", "our", "older", "younger", "oldest", "youngest", "little"}
NOTE_VERBS = set("has have had takes take is was are lives uses owns keeps keep kept allergic prefers gets needs can "
                 "cannot can't does doesn't doesn’t no not never works drives wears sleeps eats drinks likes call calls "
                 "name named type pregnant diabetic born moved sold bought plans wants knows speaks stays goes grew "
                 "always usually most should must avoid avoids on in at with from".split())


def _subject(note):
    """Who a note is about: the household words and names it starts with ("Daughter Maya (7) is..." gives {daughter,
    maya}, "Ana takes insulin." {ana}), and nobody for a note about the person ("Allergic to penicillin.")."""
    subject = set()
    for word in re.findall(r"[A-Za-z][\w'’-]*", note):
        low = word.lower()
        if FAMILY.fullmatch(low):
            subject.add(re.sub(r"ren$|ies$|s$", lambda m: "y" if m.group() == "ies" else "", low))
        elif low in SUBJECT_SKIP:
            continue
        elif word[0].isupper() and low not in NOTE_VERBS:
            subject.add(low)
        else:
            break
    return frozenset(subject)


def _same_person(a, b):
    """Whether two notes are about the same person: both about them, or naming the same one ("Maya" and "Daughter
    Maya")."""
    sa, sb = _subject(a), _subject(b)
    return sa == sb or bool(sa and sb and (sa <= sb or sb <= sa))


def _same_shape(a, b):
    """Whether two notes are about the same person and say it the same way round ("not allergic" isn't "allergic")."""
    return _same_person(a, b) and bool(NEGATED.search(a)) == bool(NEGATED.search(b))


class Memory:
    def __init__(self, path, settings_path):
        self.path, self.settings_path = path, settings_path
        self.lock = threading.Lock()

    def notes(self):
        return self._read()

    def _read(self, strict=False):
        """The notes. strict: raise when the file is there but can't be read, rather than answer none, so a change
        made while another program holds the file can't save over every note."""
        for attempt in range(40):
            try:
                with open(self.path, "rb") as f:
                    return parse(_decode(f.read()), header=True)
            except FileNotFoundError:
                return []
            except PermissionError:
                if os.name == "nt" and attempt < 39:  # Windows: a virus scan or backup has it open for a moment
                    time.sleep(0.05)
                    continue
                if strict:
                    raise
                return []
            except OSError:
                if strict:
                    raise
                return []

    def _write(self, notes):
        _write_file(self.path, HEADER + "".join(n + "\n" for n in notes))

    # ---- the person's switch: may the AI add and change notes? ----
    def _settings(self):
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    @property
    def ai_writes(self):
        return self._settings().get("memory_ai_writes", True) is not False

    def set_ai_writes(self, on):
        self.set_setting("memory_ai_writes", bool(on))

    def set_setting(self, key, value):
        """Keep one of the app's settings in the same file (None removes it), such as a folder the person picked."""
        with self.lock:
            data = self._settings()
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
            _write_file(self.settings_path, json.dumps(data, indent=1))

    # ---- the person's edits ----
    def save_text(self, text, base=None):
        """Save the person's version of the notes. base is the text they started editing from: notes the AI added
        since then are kept, after theirs, and notes it deleted or changed since then, which they left as they were,
        stay deleted or changed. Returns (notes, kept, dropped)."""
        mine = parse(text)
        with self.lock:
            current = self._read(strict=True)
            kept, dropped = [], []
            if base is not None:
                was = {n.lower() for n in parse(base)}
                now = {n.lower() for n in current}
                dropped = [n for n in mine if n.lower() in was and n.lower() not in now]
                mine = [n for n in mine if n not in dropped]
                theirs = {n.lower() for n in mine} | {n.lower() for n in dropped}
                kept = [n for n in current if n.lower() not in was and n.lower() not in theirs]
            notes = mine + kept
            self._write(notes)
        return notes, kept, dropped

    def undo(self, action, note="", old="", at=None, before=(), after=()):
        """Take back one change the AI made (the event it reported). Returns whether there was anything to undo."""
        note, old = clean(note), clean(old)
        with self.lock:
            notes = self._read(strict=True)
            keys = [n.lower() for n in notes]
            if action == "add" and note.lower() in keys:
                del notes[keys.index(note.lower())]
            elif action == "change" and note.lower() in keys and old:
                if old.lower() in keys:  # the old note is back already: just take the new one out
                    del notes[keys.index(note.lower())]
                else:
                    notes[keys.index(note.lower())] = old
            elif action == "delete" and old and old.lower() not in keys:
                # Back where it was: before the first note that followed it, or after the last one before it, that is
                # still there (positions shift when several went at once).
                before, after = ([x] if isinstance(x, str) and x else list(x) if isinstance(x, list) else []
                                 for x in (before, after))
                where = None
                for k in range(max(len(before), len(after))):  # the nearest neighbour still there, on either side
                    b = clean(before[k]).lower() if k < len(before) else ""
                    a = clean(after[-1 - k]).lower() if k < len(after) else ""
                    if b in keys:
                        where = keys.index(b)
                        break
                    if a in keys:
                        where = keys.index(a) + 1
                        break
                if where is None:
                    where = at if isinstance(at, int) and 0 <= at <= len(notes) else len(notes)
                notes.insert(where, old)
            else:
                return False
            self._write(parse("\n".join(notes)))
        return True

    # ---- the AI's changes (core.memory_check) ----
    def apply(self, plan):
        """Make the changes the model asked for after an answer. Yields an event for each one made."""
        if not self.ai_writes:  # the person may have turned it off while the model was deciding
            return
        snapshot = self.notes()  # as they were before this step: where a deleted note sat, and which note a text names

        def key(text):  # the note a text names, so another wording of it isn't taken for a different, similar note
            i = _find(clean(text), snapshot)
            return snapshot[i].lower() if i is not None else clean(text).rstrip(" .").lower()

        gone = []  # notes deleted or rewritten here, which a "remember" list repeating every note mustn't bring back
        rewritten = {key(c["old"]) for c in plan["change"] if _rewrites(c)}
        handled = set()  # each note acted on once
        for note in plan["forget"]:
            if key(note) in handled or key(note) in rewritten:  # an update of the same note keeps what's left of it
                continue
            handled.add(key(note))
            event = self.change(note, "", snapshot)
            if event:
                gone.append((event["old"], event.get("note", "")))
                yield event
        for c in plan["change"]:
            extra = _tacked_on(c["old"], c["new"])
            if key(c["old"]) in handled:  # deleted already: only a fact added to its end still counts
                event = self.add(extra) if extra else None
            elif extra:  # an unrelated fact added to the end of an old note: save it as a note of its own
                handled.add(key(c["old"]))
                event = self.add(extra)
            else:
                handled.add(key(c["old"]))
                event = self.change(c["old"], c["new"], snapshot, keep=not plan.get("asked_forget"))
                if event is None and not NOTHING.match(tidy(clean(c["new"]))):
                    event = self.add(c["new"])  # the old note wasn't found: keep the new fact anyway
            if event:
                gone += [(event["old"], event.get("note", ""))] if event.get("old") else []
                yield event
        for note in plan["remember"]:
            if any(self._repeats(note, g, rewrite) for g, rewrite in gone):
                continue
            event = self.add(note)
            if event:
                yield event

    @staticmethod
    def _repeats(note, gone, rewrite=""):
        """Whether a note the model wants to remember only brings back one this step deleted or rewrote (Granite lists
        every note again after a deletion). What a rewrite left out, as a note of its own, isn't a repeat."""
        words, had = _words(note), _words(gone)
        if not words or not words <= had or not _same_shape(note, gone):
            return False
        return not rewrite or words == had or words <= _words(rewrite)

    def add(self, note):
        """Save a note the AI wrote. Returns the event for the screen, or None when there was nothing to save. A note
        that says everything an old one does, and more, replaces it; one that adds nothing new is left out; one that
        says an old one the other way round ("Is allergic to penicillin." for "Is not allergic...") corrects it. Only
        notes about the same person count: "Daughter Maya is allergic to penicillin." leaves "Allergic to
        penicillin." alone."""
        note = tidy(clean(note))
        if not _usable(note):
            return None
        new = _words(note)
        with self.lock:
            notes = self._read(strict=True)
            for i, n in enumerate(notes):
                old = _words(n)
                if n.lower() == note.lower():
                    return None
                if not _same_person(n, note):
                    continue
                if not _same_shape(n, note):
                    if not (old and old == new):
                        continue
                elif new and new <= old:
                    return None
                if old and old <= new:
                    if size(notes) - len(n) + len(note) > MAX_CHARS:
                        return {"type": "memory", "action": "full", "note": note}
                    notes[i] = note
                    self._write(parse("\n".join(notes)))
                    return {"type": "memory", "action": "change", "note": note, "old": n}
            if size(notes) + len(note) + 1 > MAX_CHARS:
                return {"type": "memory", "action": "full", "note": note}
            notes.append(note)
            self._write(notes)
        return {"type": "memory", "action": "add", "note": note}

    def change(self, old, new, snapshot=None, keep=False):
        """Rewrite the note old names as new, or delete it when new is empty. Returns the event, or None. snapshot: the
        notes before a series of changes, for where a deleted note sat among them. keep: the person didn't ask to
        forget anything, so a separate fact the rewrite would drop stays (_with_kept)."""
        old, new = clean(old), tidy(clean(new))
        if NOTHING.match(new):
            new = ""  # a model "changing" a note to "No location stored." means deleting it
        if not old or (new and not _usable(new)):
            return None
        with self.lock:
            notes = self._read(strict=True)
            i = _find(old, notes)
            if i is None:
                return None
            was = notes[i]
            new, beside = _narrowed(was, old, new)
            if keep and new and not beside:
                new = _with_kept(was, new)
            if new is None or new.rstrip(" .").lower() == was.rstrip(" .").lower():  # not just a full stop added
                return None
            if not beside:
                if new and any(n.lower() == new.lower() for n in notes):
                    new = ""  # it would now say what another note says: that one stays, this one goes
                if new and size(notes) - len(was) + len(new) > MAX_CHARS:
                    return {"type": "memory", "action": "full", "note": new}
                ref = snapshot if snapshot is not None else list(notes)
                j = next((k for k, n in enumerate(ref) if n.lower() == was.lower()), None)
                near = {"before": ref[j + 1:], "after": ref[:j]} if j is not None else {"before": notes[i + 1:],
                                                                                        "after": notes[:i]}
                if new:
                    notes[i] = new
                else:
                    del notes[i]
                self._write(notes)
        if beside:
            return self.add(new)
        if new:
            return {"type": "memory", "action": "change", "note": new, "old": was}
        return {"type": "memory", "action": "delete", "old": was, "at": i, **near}


FACT_START = re.compile(r"(?:is|are|was|has|have|takes|take|can|can['’]t|cannot|must|needs|uses|should|doesn['’]t|does|"
                        r"allergic|never)\b", re.I)


def _with_kept(was, new):
    """A rewrite of a whole note that drops a separate fact it held keeps that fact: "Takes 40 mg lisinopril." for
    "Takes 20 mg lisinopril and is allergic to sulfa drugs." becomes "Takes 40 mg lisinopril and is allergic to sulfa
    drugs."."""
    parts = re.split(r"\s+and\s+|;\s*", was.rstrip(" ."))
    kept = [p.strip() for p in parts[1:] if FACT_START.match(p.strip()) and len(_words(p)) >= 2
            and not _words(p) & _words(new)]
    return new if not kept else new.rstrip(" .") + "".join(f" and {p}" for p in kept) + "."


def _narrowed(was, old, new):
    """What a change does to the note was when old names only part of it ("Takes 20 mg lisinopril" in "Takes 20 mg
    lisinopril and is allergic to sulfa drugs."): (new, False) to change just that part, (new, True) to keep the note
    and save new beside it, or (None, False) to leave it alone, so the allergy isn't lost with the dose."""
    part = old.rstrip(" .")
    if was.rstrip(" .").lower() == part.lower():
        return new, False
    untouched = [c for c in CLAUSE.split(was) if _words(c) and not _words(c) & _words(old)]
    k = was.lower().find(part.lower())
    if new and k >= 0:
        rest = was[k + len(part):].strip(" .")
        if rest and rest.lower() in new.lower():  # new is already the whole rewritten note
            return new, False
        return re.sub(r"\.\.+$", ".", (was[:k] + new.rstrip(" .") + was[k + len(part):]).strip()), False
    if not untouched:
        return new, False
    return (new, True) if new else (None, False)


def prompt_section(notes, ai_writes, files=(), today=None):
    """What the model is told about memory at the start of a chat, added after its instructions.
    ai_writes: whether the model updates its notes after answers (the person allows it).
    files: (name, title) of the person's own files."""
    out = []
    if today:
        out.append(f"Today is {today:%A}, {today:%B} {today.day}, {today.year}.")
    files = list(files)
    if files:
        shown = [name + (f' ("{title}")' if title and title != name and len(title) < 80 else "")
                 for name, title in files[:MAX_FILES_LISTED]]
        more = f", and {len(files) - MAX_FILES_LISTED} more" if len(files) > MAX_FILES_LISTED else ""
        out.append("The person's own files, which you search along with the library: " + "; ".join(shown) + more + ".")
    if notes or ai_writes:
        listing = "\n".join(f"- {n}" for n in notes) if notes else "(none yet)"
        out.append("Memory: your notes about this person, kept between chats. They can read and edit them "
                   "(Memory, at the top of the window). These are your notes, not part of their files or the library, "
                   f"so don't say a file or article says what only a note does.\n{listing}")
    if notes or ai_writes:
        rules = ["Use a note when it bears on the question (an allergy, a medicine, who is in the household, what "
                 "equipment they have), and leave the rest alone."]
        if ai_writes:
            rules += ["After each answer the app gives you a moment to update these notes from what the person said, "
                      "so when they tell you something about themselves, just answer as usual; the app shows them what "
                      "changed. When they only ask you to remember or forget something, don't search: just say \"OK, "
                      "I'll remember that.\" or \"OK, I'll forget that.\"",
                      "When one of their files comes up and your notes don't say what it is or how much it matters, "
                      "you may ask about it in one short question just before your Sources line."]
        else:
            rules.append("The person keeps these notes; you can't change them.")
        out.append("\n".join(f"- {r}" for r in rules))
    return "\n\n".join(out)
