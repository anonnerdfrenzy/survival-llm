"""Extra sources the app can add to an installed library from its Library window, and take out again (stdlib only).

Each is downloaded from its own website, not from the library packs: some may not be shared, so they never go in a
pack (see SOURCES.md), but anyone may add them to their own copy. The app remembers which ones were added
(settings.json "addons") and adds them again after a new library pack replaces the library folder.

To offer another: write a function that downloads it and returns its articles as [{"title", "url", "text"}] (text in
Markdown, see library/fetch_agorismewiki.py), and add an entry below. build_library.py builds the same sources into
personal libraries from library.noindex/raw/<key>/.
"""
import os
import sqlite3

from library import writer

MIN_CHARS = 300  # shorter pages are stubs, as in build_library.py


def _agorismewiki():
    from library import fetch_agorismewiki
    return fetch_agorismewiki.articles(timeout=60)


ADDONS = {
    "agorismewiki": {
        "name": "Agorisme wiki",
        "label": "Agorisme wiki (Dutch: self-sufficiency, food storage, water, energy, local economy)",
        "about": "In Dutch: self-sufficiency, food storage, water, energy and the local economy. About 40 articles, "
                 "under 1 MB.",
        "language": "nl",
        "topic": "howto",
        "url": "https://agorismewiki.nl",
        "license": "No license stated by agorismewiki.nl (checked 2026-11-07): for personal use only, not shared in "
                   "the library downloads. Agorisme wiki contributors https://gitlab.com/softwarehuis/agorisme",
        "note": "For your own use: the site states no license, so it is never in the library downloads.",
        "fetch": _agorismewiki,
    },
}


def download(key):
    """The add-on's articles, from its website: [(title, url, text)], stubs left out. Raises OSError when offline,
    RuntimeError when the site answered with nothing usable."""
    found = [(a["title"], a["url"], a["text"]) for a in ADDONS[key]["fetch"]() if len(a["text"]) >= MIN_CHARS]
    if not found:
        raise RuntimeError(f"{ADDONS[key]['name']} had no articles. Its website may have changed.")
    return found


def install(lib_dir, key, articles):
    """Put an add-on's articles in the library at lib_dir, replacing any copy already there. Returns how many. The
    caller makes sure nothing else has the index open (the app closes its copies first)."""
    addon, text_dir = ADDONS[key], os.path.join(lib_dir, "text")
    db = writer.open_db(os.path.join(lib_dir, "index.sqlite"))
    try:
        writer.drop_source(db, key, text_dir)
        db.execute("BEGIN")
        try:
            source_id = db.execute("INSERT INTO sources(key, label, topic, origin, license) VALUES(?,?,?,?,?)",
                                   (key, addon["label"], addon["topic"], addon["url"], addon["license"])).lastrowid
            out = writer.SourceWriter(db, source_id, key, addon["label"], text_dir)
            for title, url, text in articles:
                out.add(title, url, text)
            out.close()
            db.execute("UPDATE sources SET docs=?, done=1 WHERE id=?", (out.docs, source_id))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        _settle(db)
        return out.docs
    finally:
        db.close()


def remove(lib_dir, key):
    """Take an add-on out of the library at lib_dir."""
    db = writer.open_db(os.path.join(lib_dir, "index.sqlite"))
    try:
        writer.drop_source(db, key, os.path.join(lib_dir, "text"))
        _settle(db)
    finally:
        db.close()


def _settle(db):
    """Back to one self-contained file, as the packs ship it, so read-only copies open cleanly."""
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    try:
        db.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
