"""Writing sources into a library: the text shards and the search index (stdlib only).

Shared by library/build_library.py, which builds whole libraries, and the app, which adds and removes the extra
sources in library/addons.py from its Library window. A source's articles go in text/<key>/NNNN.md (plain-text
Markdown shards of about 16 MB) and index.sqlite (SQLite FTS5 over ~1,500-character passages).
"""
import os
import shutil
import sqlite3

from library.passages import split_passages

SHARD_BYTES = 16 * 1024 * 1024


class SourceWriter:
    def __init__(self, db, source_id, key, label, text_dir):
        self.db, self.source_id, self.label, self.text_dir = db, source_id, label, text_dir
        self.dir = os.path.join(self.text_dir, key)
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        self.key, self.shard, self.f, self.pos, self.file_id, self.docs = key, -1, None, 0, None, 0

    def _next_shard(self):
        if self.f:
            self.f.close()
        self.shard += 1
        rel = f"{self.key}/{self.shard:04d}.md"
        self.f = open(os.path.join(self.text_dir, rel), "wb")
        self.pos = 0
        self.file_id = self.db.execute("INSERT INTO files(path) VALUES(?)", (rel,)).lastrowid

    def _write(self, s):
        b = s.encode("utf-8")
        self.f.write(b)
        self.pos += len(b)
        return len(b)

    def add(self, title, url, text):
        if self.f is None or self.pos > SHARD_BYTES:
            self._next_shard()
        start = self.pos
        self._write(f"# {title}\nSource: {self.label}" + (f" | {url}" if url else "") + "\n\n")
        passages = []
        for heading, chunk in split_passages(text):
            offset = self.pos
            passages.append((offset, self._write(chunk), heading, chunk))
            self._write("\n\n")
        self._write("---\n\n")
        doc_id = self.db.execute(
            "INSERT INTO docs(source_id, title, url, file_id, offset, length) VALUES(?,?,?,?,?,?)",
            (self.source_id, title, url, self.file_id, start, self.pos - start)).lastrowid
        for offset, length, heading, chunk in passages:
            pid = self.db.execute("INSERT INTO passages(doc_id, offset, length) VALUES(?,?,?)",
                                  (doc_id, offset, length)).lastrowid
            self.db.execute("INSERT INTO fts(rowid, title, body) VALUES(?,?,?)",
                            (pid, f"{title} {heading}".strip(), chunk))
        self.docs += 1

    def close(self):
        if self.f:
            self.f.close()


def open_db(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=OFF;
        CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, key TEXT UNIQUE, label TEXT, topic TEXT,
                                           origin TEXT, docs INT DEFAULT 0, done INT DEFAULT 0, license TEXT);
        CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, path TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, source_id INT, title TEXT, url TEXT,
                                        file_id INT, offset INT, length INT);
        CREATE INDEX IF NOT EXISTS docs_title ON docs(title COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY, doc_id INT, offset INT, length INT);
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, body, content='', contentless_delete=1,
                                                          tokenize='porter unicode61 remove_diacritics 2');
    """)
    if "license" not in [c[1] for c in db.execute("PRAGMA table_info(sources)")]:
        db.execute("ALTER TABLE sources ADD COLUMN license TEXT")  # libraries built before licenses were kept
    return db


def drop_source(db, key, text_dir):
    """Remove one source from the index and disk so the next build redoes it."""
    row = db.execute("SELECT id FROM sources WHERE key=?", (key,)).fetchone()
    if row:
        db.execute("BEGIN")
        db.execute("DELETE FROM fts WHERE rowid IN (SELECT p.id FROM passages p JOIN docs d ON d.id = p.doc_id "
                   "WHERE d.source_id=?)", row)
        db.execute("DELETE FROM passages WHERE doc_id IN (SELECT id FROM docs WHERE source_id=?)", row)
        db.execute("DELETE FROM files WHERE id IN (SELECT DISTINCT file_id FROM docs WHERE source_id=?)", row)
        db.execute("DELETE FROM docs WHERE source_id=?", row)
        db.execute("DELETE FROM sources WHERE id=?", row)
        db.execute("COMMIT")
    shutil.rmtree(os.path.join(text_dir, key), ignore_errors=True)
