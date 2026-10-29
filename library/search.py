"""Read-only search over the offline library built by build_library.py (stdlib only)."""
import json
import os
import re
import sqlite3
import sys


def app_dir():
    """The app's settings folder (app/server.py keeps its settings, memory and indexes there)."""
    if os.environ.get("SURVIVAL_LLM_APP_DIR"):
        return os.environ["SURVIVAL_LLM_APP_DIR"]
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "Survival LLM")
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", home), "Survival LLM")
    return os.path.join(home, ".survival-llm")


def chosen_folder(key):
    """A folder the person picked in the app: "library_dir" (the library) or "files_dir" (Your files)."""
    try:
        with open(os.path.join(app_dir(), "settings.json"), encoding="utf-8") as f:
            value = json.load(f).get(key)
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and os.path.isabs(value) else None


def default_library():
    """Where a new library goes: out of sight, with the app's other data (issue #9). On a Mac the ".noindex" keeps
    Spotlight from indexing a million articles; on Windows it goes in the local (not roaming) app data folder."""
    if os.name == "nt":
        return os.path.join(os.environ.get("LOCALAPPDATA") or app_dir(), "Survival LLM", "Library")
    return os.path.join(app_dir(), "Library.noindex" if sys.platform == "darwin" else "Library")


def _find_library():
    """$SURVIVAL_LLM_LIBRARY; else the folder picked in the app; else a library in ~/Survival LLM Library (where
    libraries went before 0.4) or the library.noindex next to this code; else the place for a new one."""
    if os.environ.get("SURVIVAL_LLM_LIBRARY"):  # an explicit choice wins, even before anything is installed
        return os.environ["SURVIVAL_LLM_LIBRARY"]
    chosen = chosen_folder("library_dir")
    if chosen:
        return chosen
    dev = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library.noindex"))
    home = os.path.join(os.path.expanduser("~"), "Survival LLM Library")
    if os.path.exists(home + ".download"):  # an older version's download, not finished: carry on with it there
        return home
    for path in (home, dev):
        if os.path.exists(os.path.join(path, "index.sqlite")):
            return path
    return default_library()


LIB = _find_library()
DB_PATH = os.path.join(LIB, "index.sqlite")
TEXT_DIR = os.path.join(LIB, "text")
TOPICS = ("medical", "emergency", "howto", "repair", "encyclopedia")

# Ranking boost for sources with editorial review over wikiHow and Q&A sites.
OFFICIAL = ("ready-gov", "cdc-travel", "medlineplus", "nhs-medicines", "military-medicine", "wikem",
            "medical-library", "water", "post-disaster", "food-prep", "survival-manuals", "first-aid-guides",
            "usda-canning", "risk")
AUTHORITY = {**{k: 1.3 for k in OFFICIAL}, "wikipedia": 1.15, "wikimed": 1.15}
# Sources published by a government health/emergency agency, the IFRC or WHO: shown with an "Official" label.
# (Not the UK medicines guide: the NHS terms say an unrefreshed copy must not be presented as the NHS's.)
OFFICIAL_LABEL = {"ready-gov", "cdc-travel", "medlineplus", "military-medicine", "survival-manuals",
                  "first-aid-guides", "usda-canning"}

STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here
hers herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off on
once only or other our ours ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were what when where which
while who whom why will with would you your yours yourself yourselves""".split())


def use_folder(path):
    """Read the library from path from now on (the app moved it, or the person picked another one)."""
    global LIB, DB_PATH, TEXT_DIR
    LIB, DB_PATH, TEXT_DIR = path, os.path.join(path, "index.sqlite"), os.path.join(path, "text")


class Library:
    def __init__(self, path=None):
        path = path or DB_PATH
        # check_same_thread=False only so a library swap can close it from another thread (see app/server.py)
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        try:
            self.db.execute("SELECT 1 FROM sources LIMIT 1")
        except sqlite3.OperationalError:  # e.g. a WAL-mode file on a read-only disk
            self.db = sqlite3.connect(f"file:{path}?immutable=1", uri=True, check_same_thread=False)

    def stats(self):
        """(articles, sources) that are fully indexed."""
        sources, docs = self.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(docs), 0) FROM sources WHERE done=1").fetchone()
        return docs, sources

    def labels(self):
        """Names of the indexed sources, largest first, for telling the model what it can search."""
        return [r[0] for r in self.db.execute("SELECT label FROM sources WHERE done=1 ORDER BY docs DESC")]

    def _read(self, file_id, offset, length):
        return self._read_bytes(file_id, offset, length).decode("utf-8", "replace")

    def search(self, query, topic=None, limit=8, scores=False):
        """Best passages for a keyword query, at most one per article. scores=True adds each result's ranking
        score (lower is better) and how many of the query's words its passage contains, for merging result lists."""
        words = query_words(query)
        if not words:
            return []
        terms = ['"' + w.replace('"', "") + '"' for w in words]
        hits = []
        for joiner in (" ", " OR "):  # all words first; any word if that finds too little
            hits = self.db.execute(
                "SELECT rowid, rank FROM fts WHERE fts MATCH ? AND rank MATCH 'bm25(4.0, 1.0)' "
                "ORDER BY rank LIMIT 300", (joiner.join(terms),)).fetchall()
            if len(hits) >= 3 or len(words) == 1:
                break
        if not hits:
            return []
        rank = dict(hits)
        marks = ",".join("?" * len(rank))
        info = {r[0]: r for r in self.db.execute(
            "SELECT p.id, d.id, d.title, s.label, s.topic, d.file_id, p.offset, p.length, s.key, d.offset, d.length "
            f"FROM passages p JOIN docs d ON d.id = p.doc_id JOIN sources s ON s.id = d.source_id "
            f"WHERE p.id IN ({marks})", list(rank))}
        # BM25 ranks are negative (lower is better), so a weight above 1 moves a source up.
        order = sorted(info, key=lambda pid: rank[pid] * AUTHORITY.get(info[pid][8], 1.0))
        results, seen_docs, shown = [], set(), set()
        for pid in order:
            r = info[pid]
            if r[1] in seen_docs or (topic and topic != "any" and r[4] != topic):
                continue
            seen_docs.add(r[1])
            body = self._read_bytes(r[5], r[9], r[10]).split(b"\n\n", 1)[-1]  # the article without its title header
            if body in shown:  # the same article under another title (iFixit's guides for each model variant)
                continue
            shown.add(body)
            text = self._read(r[5], r[6], r[7])
            results.append({"id": pid, "title": r[2], "source": r[3], "official": r[8] in OFFICIAL_LABEL,
                            "snippet": _snippet(text, words)})
            if scores:
                low = f"{r[2]} {text}".lower()
                results[-1].update(score=rank[pid] * AUTHORITY.get(r[8], 1.0),
                                   matched=sum(w[:5] in low for w in words))
            if len(results) >= limit:
                break
        return results

    def read(self, passage_id, max_chars=5000):
        """Article text starting at a passage, about max_chars long."""
        row = self.db.execute(
            "SELECT p.doc_id, d.title, s.label, d.url, d.file_id, s.key FROM passages p JOIN docs d ON d.id = p.doc_id "
            "JOIN sources s ON s.id = d.source_id WHERE p.id=?", (passage_id,)).fetchone()
        if not row:
            return None
        doc_id, title, label, url, file_id, key = row
        parts, size, next_id = [], 0, None
        for pid, offset, length in self.db.execute(
                "SELECT id, offset, length FROM passages WHERE doc_id=? AND id>=? ORDER BY id", (doc_id, passage_id)):
            if parts and size + length > max_chars:
                next_id = pid
                break
            parts.append(self._read(file_id, offset, length))
            size += length
        return {"title": title, "source": label, "url": url, "official": key in OFFICIAL_LABEL,
                "text": "\n\n".join(parts), "next_id": next_id}


    def document(self, passage_id):
        """The whole article holding a passage, split into passages so a viewer can mark the cited one."""
        row = self.db.execute(
            "SELECT d.id, d.title, s.label, d.url, d.file_id, d.offset, d.length, s.key FROM passages p "
            "JOIN docs d ON d.id = p.doc_id JOIN sources s ON s.id = d.source_id WHERE p.id=?",
            (passage_id,)).fetchone()
        if not row:
            return None
        doc_id, title, label, url, file_id, start, length, key = row
        raw = self._read_bytes(file_id, start, length)
        parts = [{"id": pid, "text": raw[off - start:off - start + n].decode("utf-8", "replace")}
                 for pid, off, n in self.db.execute(
                     "SELECT id, offset, length FROM passages WHERE doc_id=? ORDER BY id", (doc_id,))]
        return {"doc_id": doc_id, "title": title, "source": label, "url": url, "official": key in OFFICIAL_LABEL,
                "license": self.license(key), "focus": passage_id, "parts": parts}

    def license(self, key):
        """The source's license line, from libraries built since licenses were kept ('' before that)."""
        try:
            row = self.db.execute("SELECT license FROM sources WHERE key=?", (key,)).fetchone()
        except sqlite3.OperationalError:  # no license column yet
            return ""
        return (row and row[0]) or ""

    def _read_bytes(self, file_id, offset, length):
        (path,) = self.db.execute("SELECT path FROM files WHERE id=?", (file_id,)).fetchone()
        with open(os.path.join(TEXT_DIR, path), "rb") as f:
            f.seek(offset)
            return f.read(length)


def query_words(query):
    """The words of a query worth searching for."""
    return [w for w in re.findall(r"[\w']+", query.lower()) if w not in STOPWORDS and len(w) > 1][:12]


def _snippet(text, words, width=360):
    flat = " ".join(line.lstrip("#").strip() for line in text.splitlines() if line.strip())
    low = flat.lower()
    hits = [low.find(w) for w in words if low.find(w) >= 0]
    start = max(0, min(hits) - 80) if hits else 0
    out = flat[start:start + width]
    return ("..." if start else "") + out + ("..." if start + width < len(flat) else "")
