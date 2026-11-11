"""The person's own files: documents they add (PDF, Word, EPUB, web pages, text), searched along with the library.

The folder is the record. Files put in it, by the app or by hand, are read into a small index of their own (kept
with the app's settings, so installing a new library pack never touches it), and taken out again when they leave
the folder. Text comes out with the standard library, except PDFs, which need pypdf (bundled with the app).
"""
import html.parser
import os
import posixpath
import re
import sqlite3
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

from library.passages import split_passages
from library.search import Library, query_words

KEY = "my-files"
LABEL = "Your files"
ID_OFFSET = 1_000_000_000  # their passages get ids above the library's, so one id names one passage
KINDS = {".pdf": "PDF", ".docx": "Word", ".odt": "OpenDocument", ".epub": "EPUB", ".html": "web page",
         ".htm": "web page", ".txt": "text", ".md": "text", ".markdown": "text", ".csv": "text",
         ".jpg": "photo", ".jpeg": "photo", ".png": "photo", ".tif": "photo", ".tiff": "photo", ".bmp": "photo"}
IMAGES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")
CANT_READ = ("Survival LLM can't read this kind of file. It reads PDF, Word, EPUB, web pages, text files and, on "
             "Windows, photos and scans.")
MAX_TEXT = 50_000_000  # characters kept from one file (a 1,000-page book is about 3 million)
IGNORED = re.compile(r"^(\.|~\$)|^(desktop\.ini|thumbs\.db|icon\r)$|\.(part|crdownload|download|tmp)$", re.I)

SCHEMA = """
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT, topic TEXT,
                                       origin TEXT, docs INT DEFAULT 0, done INT DEFAULT 0, license TEXT);
    CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT, data BLOB);
    CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INT, title TEXT, url TEXT,
                                    file_id INT, offset INT, length INT);
    CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INT, offset INT, length INT);
    CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, body, content='', contentless_delete=1,
                                                      tokenize='porter unicode61 remove_diacritics 2');
    CREATE TABLE IF NOT EXISTS items(name TEXT PRIMARY KEY, size INT, mtime REAL, doc_id INT, status TEXT,
                                     error TEXT, title TEXT, passages INT, added REAL);
"""


class Unreadable(Exception):
    """A file we can't get text out of; the message is shown to the person."""


# ---------- searching ----------

class MyFiles(Library):
    """Their index: the library's tables, with each document's text stored in the database itself."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)

    @classmethod
    def open(cls, path):
        """Their index, or None when no file of theirs is ready to search."""
        if not os.path.exists(path):
            return None
        try:
            mine = cls(path)
            if mine.stats()[0]:
                return mine
            mine.db.close()
        except sqlite3.Error:  # created but not set up yet, or damaged (the next sync rebuilds it)
            pass
        return None

    def license(self, key):
        return ""

    def _read_bytes(self, file_id, offset, length):
        row = self.db.execute("SELECT substr(data, ?, ?) FROM files WHERE id=?", (offset + 1, length, file_id)).fetchone()
        return row[0] if row and row[0] is not None else b""  # empty if the file was re-read meanwhile


class Combined:
    """The library plus their files, searched as one. Either part may be missing."""

    def __init__(self, main, mine):
        self.main, self.mine = main, mine
        self.has_personal = mine is not None

    def _part(self, pid):
        return (self.mine, pid - ID_OFFSET) if pid >= ID_OFFSET else (self.main, pid)

    def stats(self):
        return self.main.stats() if self.main else (0, 0)

    def labels(self):
        return ([LABEL + " (documents the person added)"] if self.mine else []) + (self.main.labels() if self.main else [])

    def search(self, query, topic=None, limit=8):
        """Their files first when a passage has most of the query's words, then the library, then their weaker matches.
        (Scores from a handful of files and from a million articles can't be compared directly.)"""
        mine = self.mine.search(query, limit=limit, scores=True) if self.mine else []  # any topic: they're theirs
        main = self.main.search(query, topic=topic, limit=limit) if self.main else []
        need = max(1, round(len(query_words(query)) * 0.6))
        strong = [r for r in mine if r["matched"] >= need][:3]
        weak = [r for r in mine if r not in strong]
        for r in mine:
            r["id"] += ID_OFFSET
            del r["score"], r["matched"]
        return (strong + main + weak)[:limit]

    def read(self, passage_id, max_chars=5000):
        part, pid = self._part(passage_id)
        doc = part.read(pid, max_chars) if part and pid > 0 else None
        if doc and part is self.mine and doc["next_id"]:
            doc["next_id"] += ID_OFFSET
        return doc

    def document(self, passage_id):
        part, pid = self._part(passage_id)
        doc = part.document(pid) if part and pid > 0 else None
        if doc and part is self.mine:
            doc["focus"] += ID_OFFSET
            for p in doc["parts"]:
                p["id"] += ID_OFFSET
        return doc


# ---------- keeping the index in step with the folder ----------

progress = {"busy": False, "doing": "", "done": 0, "total": 0}
_lock = threading.Lock()
_again = threading.Event()


def open_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, isolation_level=None, timeout=30)
    db.executescript(SCHEMA)
    if not db.execute("SELECT 1 FROM sources WHERE key=?", (KEY,)).fetchone():
        db.execute("INSERT INTO sources(key, label, topic, origin, done) VALUES(?,?,NULL,'',1)", (KEY, LABEL))
    return db


def items(db_path):
    """What the index knows about each file, for the app's list."""
    if not os.path.exists(db_path):
        return []
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute("SELECT name, status, error, title, passages, size, mtime FROM items ORDER BY added DESC, name")
        return [dict(zip(("name", "status", "error", "title", "passages", "size", "mtime"), r)) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        db.close()


def sync(folder, db_path):
    """Read new or changed files in folder and drop the ones that left it. Returns True if the index changed.
    If a sync is already running, it looks at the folder again when it finishes, instead of running twice."""
    if not _lock.acquire(blocking=False):
        _again.set()
        return False
    changed = False
    try:
        progress.update(busy=True, doing="", done=0, total=0)
        while True:
            _again.clear()
            try:
                changed = _sync_once(folder, db_path) or changed
            except sqlite3.DatabaseError as exc:
                if isinstance(exc, sqlite3.OperationalError):  # busy or locked: try again next time
                    raise
                for suffix in ("", "-wal", "-shm"):  # damaged: it is only a copy of the folder, so start it over
                    try:
                        os.remove(db_path + suffix)
                    except OSError:
                        pass
                changed = _sync_once(folder, db_path) or True
            if not _again.is_set():
                return changed
    finally:
        progress.update(busy=False, doing="", done=0, total=0)
        _lock.release()


def _on_disk(folder):
    found = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if IGNORED.search(name):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found[os.path.relpath(path, folder).replace(os.sep, "/")] = (st.st_size, st.st_mtime)
    return found


def _sync_once(folder, db_path):
    found = _on_disk(folder) if os.path.isdir(folder) else {}
    if not found and not os.path.exists(db_path):
        return False
    db = open_db(db_path)
    try:
        known = {r[0]: (r[1], r[2]) for r in db.execute("SELECT name, size, mtime FROM items")}
        changed = False
        for name in known.keys() - found.keys():
            _drop(db, name)
            changed = True
        todo = sorted(n for n in found if known.get(n) != found[n])
        progress.update(total=len(todo))
        for i, name in enumerate(todo):
            progress.update(doing=name, done=i)
            if time.time() - found[name][1] < 2:  # maybe still being copied in: wait until it stops changing
                time.sleep(2)
                size_now = _on_disk_one(folder, name)
                if size_now != found[name]:
                    _again.set()
                    continue
            _index(db, folder, name, *found[name])
            changed = True
        if changed:
            db.execute("UPDATE sources SET docs=(SELECT COUNT(*) FROM items WHERE status='ready') WHERE key=?", (KEY,))
        return changed
    finally:
        db.close()


def _on_disk_one(folder, name):
    try:
        st = os.stat(os.path.join(folder, *name.split("/")))
        return st.st_size, st.st_mtime
    except OSError:
        return None


def _drop(db, name, keep_item=False):
    row = db.execute("SELECT doc_id FROM items WHERE name=?", (name,)).fetchone()
    db.execute("BEGIN")
    if row and row[0]:
        doc = row[0]
        db.execute("DELETE FROM fts WHERE rowid IN (SELECT id FROM passages WHERE doc_id=?)", (doc,))
        db.execute("DELETE FROM passages WHERE doc_id=?", (doc,))
        db.execute("DELETE FROM files WHERE id=(SELECT file_id FROM docs WHERE id=?)", (doc,))
        db.execute("DELETE FROM docs WHERE id=?", (doc,))
    if not keep_item:
        db.execute("DELETE FROM items WHERE name=?", (name,))
    db.execute("COMMIT")


def _index(db, folder, name, size, mtime):
    """Read one file into the index (replacing an older version), or record why it can't be read."""
    _drop(db, name, keep_item=True)
    added = time.time()
    row = db.execute("SELECT added FROM items WHERE name=?", (name,)).fetchone()
    if row and row[0]:
        added = row[0]
    status, error, title, doc_id, count = "ready", None, None, None, 0
    try:
        title, text = extract(os.path.join(folder, *name.split("/")))
        doc_id, count = _write(db, name, title, text[:MAX_TEXT])
    except Unreadable as exc:
        status, error = "unreadable", str(exc)
    except Exception:  # a damaged or unusual file: say so rather than stop reading the others
        status, error = "unreadable", "Couldn't read this file. It may be damaged, or saved in a way Survival LLM doesn't understand."
    db.execute("INSERT OR REPLACE INTO items(name, size, mtime, doc_id, status, error, title, passages, added) "
               "VALUES(?,?,?,?,?,?,?,?,?)", (name, size, mtime, doc_id, status, error, title, count, added))


def _write(db, name, title, text):
    """Store one document the way build_library.py lays out a library shard, so the reader shows it the same way."""
    source_id = db.execute("SELECT id FROM sources WHERE key=?", (KEY,)).fetchone()[0]
    out, passages = bytearray(), []
    out += f"# {title}\nSource: {LABEL} | {name}\n\n".encode()
    for heading, chunk in split_passages(text):
        b = chunk.encode("utf-8")
        passages.append((len(out), len(b), heading, chunk))
        out += b + b"\n\n"
    out += b"---\n\n"
    db.execute("BEGIN")
    try:
        file_id = db.execute("INSERT INTO files(path, data) VALUES(?,?)", (name, bytes(out))).lastrowid
        doc_id = db.execute("INSERT INTO docs(source_id, title, url, file_id, offset, length) VALUES(?,?,?,?,0,?)",
                            (source_id, title, name, file_id, len(out))).lastrowid
        for offset, length, heading, chunk in passages:
            pid = db.execute("INSERT INTO passages(doc_id, offset, length) VALUES(?,?,?)",
                             (doc_id, offset, length)).lastrowid
            db.execute("INSERT INTO fts(rowid, title, body) VALUES(?,?,?)", (pid, f"{title} {heading}".strip(), chunk))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return doc_id, len(passages)


# ---------- getting the text out ----------

def extract(path):
    """(title, text) of a file, or Unreadable with a reason the person can act on."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in KINDS:
        raise Unreadable(CANT_READ)
    title, text = {".pdf": _pdf, ".docx": _docx, ".odt": _odt, ".epub": _epub,
                   ".html": _html_file, ".htm": _html_file}.get(ext, _image if ext in IMAGES else _plain)(path)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise Unreadable("There's no text in this file.")
    if not (title or "").strip():  # no title of its own: a short first line that isn't a sentence, or the file name
        first = text.split("\n\n", 1)[0].lstrip("#").strip()
        title = first if len(first) <= 80 and "\n" not in first and not first.endswith(".") else ""
    stem = os.path.splitext(os.path.basename(path))[0].replace("_", " ").strip()
    title = " ".join((title or "").split())[:150] or stem
    return title, text


def _pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise Unreadable("Reading PDFs needs pypdf, which this copy of Survival LLM is missing.") from None
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception:
            ok = 0
        if not ok:
            raise Unreadable("This PDF is protected, so Survival LLM can't open it. Open it, print it to a new PDF "
                             "(Print, then Save as PDF), and add that copy.")
    pages = []
    for page in reader.pages:
        try:
            pages.append(_pdf_paragraphs(page.extract_text() or ""))
        except Exception:
            pages.append("")
    text = "\n\n".join(p for p in pages if p)
    if len(text) < 40:  # a scan, or photos of pages: read it with the system's OCR where there is one
        text = _ocr(path, "This PDF is pictures of pages (a scan or photo) with no text in it, and the OCR "
                          "found no readable text in it either.")
    title = ""
    try:
        title = str((reader.metadata or {}).get("/Title") or "")
    except Exception:
        pass
    title = re.sub(r"^Microsoft (Word|PowerPoint) - ", "", title).strip()
    if re.fullmatch(r"(?i)(untitled.*|document\d*|.*\.(docx?|pdf|indd))", title):
        title = ""
    return title, text


OCR_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "winocr.ps1")
NO_OCR = "Survival LLM can only read photos and scans on Windows 10 or 11, with Windows' built-in OCR."


def _ocr(path, no_text):
    """Text read off a scan or photo with Windows' own OCR engine (library/winocr.ps1); Unreadable with no_text
    when it finds nothing, or NO_OCR where there is no OCR."""
    if os.name != "nt" or not os.path.exists(OCR_SCRIPT):
        raise Unreadable(NO_OCR)
    import subprocess
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", OCR_SCRIPT, path],
                              capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        raise Unreadable(no_text) from None
    text = done.stdout.decode("utf-8", "replace").replace("\r\n", "\n").strip()
    if done.returncode != 0 or len(text) < 40:
        raise Unreadable(no_text)
    return text


def _image(path):
    return "", _ocr(path, "Windows' OCR found no readable text in this photo.")


def _pdf_paragraphs(text):
    """PDF text comes one printed line at a time: join lines into paragraphs, ending one at a short line that
    finishes a sentence, and rejoin words hyphenated across lines."""
    lines = [line.strip() for line in text.replace("\r", "").split("\n")]
    width = max((len(line) for line in lines), default=0)
    paras, cur = [], ""
    for line in lines:
        if not line:
            if cur:
                paras.append(cur)
            cur = ""
            continue
        if cur.endswith("-") and not cur.endswith(" -") and line[:1].islower():
            cur = cur[:-1] + line
        else:
            cur = f"{cur} {line}" if cur else line
        if line.endswith((".", "!", "?", ":")) and len(line) < 0.75 * width:
            paras.append(cur)
            cur = ""
    if cur:
        paras.append(cur)
    return "\n\n".join(paras)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DC = "{http://purl.org/dc/elements/1.1/}"


def _docx(path):
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml"))
        title = _xml_title(z, "docProps/core.xml")
    paras = []
    for p in body.iter(W + "p"):
        parts = []
        for el in p.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag == W + "tab":
                parts.append(" ")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        if not text:
            continue
        style = p.find(f"{W}pPr/{W}pStyle")
        style = style.get(W + "val", "") if style is not None else ""
        level = re.match(r"(?i)heading\s*(\d)", style)
        if level or style.lower() == "title":
            text = "#" * min(int(level.group(1)) if level else 1, 4) + " " + text
        elif p.find(f"{W}pPr/{W}numPr") is not None:
            text = "- " + text
        paras.append(text)
    return title, "\n\n".join(paras)


def _odt(path):
    t = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    with zipfile.ZipFile(path) as z:
        body = ET.fromstring(z.read("content.xml"))
        title = _xml_title(z, "meta.xml")
    paras = []
    for el in body.iter():
        if el.tag == t + "h":
            text = " ".join("".join(el.itertext()).split())
            if text:
                paras.append("#" * min(int(el.get(t + "outline-level") or 1), 4) + " " + text)
        elif el.tag == t + "p":
            text = " ".join("".join(el.itertext()).split())
            if text:
                paras.append(text)
    return title, "\n\n".join(paras)


def _xml_title(z, name):
    try:
        found = ET.fromstring(z.read(name)).find(f".//{DC}title")
        return (found.text or "").strip() if found is not None else ""
    except (KeyError, ET.ParseError):
        return ""


def _epub(path):
    opf_ns = "{http://www.idpf.org/2007/opf}"
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "META-INF/encryption.xml" in names and re.search(rb"\.x?html?\b", z.read("META-INF/encryption.xml")):
            raise Unreadable("This ebook is copy-protected, so Survival LLM can't read it.")
        container = ET.fromstring(z.read("META-INF/container.xml"))
        root = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
        opf = ET.fromstring(z.read(root))
        found = opf.find(f".//{DC}title")
        title = (found.text or "").strip() if found is not None else ""
        hrefs = {item.get("id"): item.get("href") for item in opf.iter(opf_ns + "item")}
        base = posixpath.dirname(root)
        chapters = []
        for ref in opf.iter(opf_ns + "itemref"):
            href = hrefs.get(ref.get("idref"))
            name = posixpath.normpath(posixpath.join(base, urllib.parse.unquote(href or "")))
            if href and name in names:
                chapters.append(_html(z.read(name).decode("utf-8", "replace"))[1])
    return title, "\n\n".join(chapters)


def _html_file(path):
    with open(path, "rb") as f:
        return _html(_decode(f.read()))


class _HTMLText(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "nav", "footer", "form", "button", "select"}
    BLOCK = {"p", "div", "section", "article", "main", "aside", "ul", "ol", "table", "tr", "blockquote", "pre",
             "dl", "dt", "dd", "figure", "figcaption", "hr", "header", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self.in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * min(int(tag[1]), 4) + " ")
        elif tag == "li":
            self.out.append("\n\n- ")
        elif tag == "br":
            self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK or tag == "li" or re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def _html(source):
    parser = _HTMLText()
    parser.feed(source)
    parser.close()
    paras, bullet = [], False
    for para in re.split(r"\n{2,}", "".join(parser.out)):
        para = " ".join(para.split())
        if para == "-":  # a list item whose text sits in its own paragraph
            bullet = True
            continue
        if para and para.strip("#"):
            paras.append(("- " if bullet and not para.startswith("#") else "") + para)
            bullet = False
    return parser.title.strip(), "\n\n".join(paras)


def _plain(path):
    with open(path, "rb") as f:
        text = _decode(f.read())
    heading = re.search(r"^#\s+(.+)$", text, re.M) if path.lower().endswith((".md", ".markdown")) else None
    return (heading.group(1) if heading else ""), text.replace("\r\n", "\n")


def _decode(data):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")
