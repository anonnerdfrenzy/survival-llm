"""Extra sources from the Library window (library/addons.py): added to an installed library, updated, removed, and
added again after a new library pack replaced the folder. No internet: the download is faked.

Usage: python3 tests/addons_test.py"""
import os
import shutil
import sys
import tempfile
import time
import urllib.error

TMP = tempfile.mkdtemp(prefix="addons-test-")
LIB = os.path.join(TMP, "library")
os.environ.update(SURVIVAL_LLM_APP_DIR=os.path.join(TMP, "settings"), SURVIVAL_LLM_FILES=os.path.join(TMP, "files"),
                  SURVIVAL_LLM_LIBRARY=LIB, OLLAMA_HOST="127.0.0.1:9")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, ROOT)
from library import addons, writer  # noqa: E402
from library.search import Library  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail!r}"))
    if not ok:
        FAILS.append(name)


def make_library():
    """A small installed library with one source of its own, as a pack would have."""
    shutil.rmtree(LIB, ignore_errors=True)
    os.makedirs(os.path.join(LIB, "text"))
    db = writer.open_db(os.path.join(LIB, "index.sqlite"))
    db.execute("BEGIN")
    sid = db.execute("INSERT INTO sources(key, label, topic, origin) VALUES('ready-gov','Ready.gov (FEMA)','emergency','')"
                     ).lastrowid
    w = writer.SourceWriter(db, sid, "ready-gov", "Ready.gov (FEMA)", os.path.join(LIB, "text"))
    w.add("Power outages", "https://www.ready.gov/power-outages", "Keep freezers closed. " * 40)
    w.close()
    db.execute("UPDATE sources SET docs=1, done=1 WHERE id=?", (sid,))
    db.execute("COMMIT")
    addons._settle(db)
    db.close()


ARTICLES = [("Voedsel bewaren", "https://agorismewiki.nl/voedsel-bewaren/", "Groenten invriezen na blancheren. " * 20),
            ("Houtstook", "https://agorismewiki.nl/houtstook/", "Droog hout stoken in een goede kachel. " * 20)]

# ---- library/addons.py on its own ----
make_library()
check("install writes the articles", addons.install(LIB, "agorismewiki", ARTICLES) == 2)
lib = Library(os.path.join(LIB, "index.sqlite"))
check("they are searchable", [r["title"] for r in lib.search("groenten invriezen")] == ["Voedsel bewaren"])
check("with their license", "No license stated" in lib.license("agorismewiki"))
check("the pack's own source is untouched", lib.stats() == (3, 2) and lib.search("freezers")[0]["title"] == "Power outages")
lib.db.close()
check("installing again replaces, not doubles", addons.install(LIB, "agorismewiki", ARTICLES[:1]) == 1)
lib = Library(os.path.join(LIB, "index.sqlite"))
check("one copy after an update", lib.stats() == (2, 2) and not lib.search("hout stoken"), lib.stats())
lib.db.close()
addons.remove(LIB, "agorismewiki")
lib = Library(os.path.join(LIB, "index.sqlite"))
check("remove takes it out, and only it", lib.stats() == (1, 1) and lib.search("freezers"))
lib.db.close()
check("its text is gone from disk", not os.path.exists(os.path.join(LIB, "text", "agorismewiki")))
check("the index is one self-contained file again", not os.path.exists(os.path.join(LIB, "index.sqlite-wal")))

# ---- through the app ----
import server  # noqa: E402

addons.ADDONS["agorismewiki"]["fetch"] = lambda: [{"title": t, "url": u, "text": x} for t, u, x in ARTICLES]


def run(addon_id, remove=False):
    key = f"library:addon:{addon_id}"
    server.start_job(key, "test", server.addon_worker, addon_id, "remove" if remove else "add")
    for _ in range(100):
        job = server.downloads.get(key)
        if job and job["status"] not in server.ACTIVE:
            return job
        time.sleep(0.05)
    return server.downloads.get(key)


make_library()
server.library()  # the app has the library open, as while someone chats
job = run("agorismewiki")
check("the app adds it while it has the library open", job["status"] == "done", job)
status = server.Handler._status(object.__new__(server.Handler))
entry = next(a for a in status["addons"] if a["id"] == "agorismewiki")
check("status shows it added", entry["articles"] == 2 and status["library"]["articles"] == 3)
check("status lists every source", [x["key"] for x in status["library"]["list"]] == ["agorismewiki", "ready-gov"])
check("the AI's instructions name it", "Agorisme wiki" in server.prompt_for({"tools"}))
check("the app remembers it", server.chosen_addons() == ["agorismewiki"])

make_library()  # a new pack replaced the library folder
server.lib_version[0] += 1
server.readd_addons("library:lite")
lib = Library(os.path.join(LIB, "index.sqlite"))
check("it comes back after a new pack", lib.stats() == (3, 2))
lib.db.close()

job = run("agorismewiki", remove=True)
status = server.Handler._status(object.__new__(server.Handler))
check("removing it from the app", job["status"] == "done"
      and next(a for a in status["addons"] if a["id"] == "agorismewiki")["articles"] == 0)
check("and forgets it", server.chosen_addons() == [])


def busy():
    raise urllib.error.HTTPError("https://gitlab.com/x", 429, "Too Many Requests", {}, None)


addons.ADDONS["agorismewiki"]["fetch"] = busy
job = run("agorismewiki")
check("a busy website says so plainly", job["status"] == "error" and "busy" in job["error"], job)
lib = Library(os.path.join(LIB, "index.sqlite"))
check("and leaves the library as it was", lib.stats() == (1, 1))
lib.db.close()


def busy_for_50_minutes():
    raise urllib.error.HTTPError("https://gitlab.com/x", 429, "Too Many Requests", {"Retry-After": "2968"}, None)


addons.ADDONS["agorismewiki"]["fetch"] = busy_for_50_minutes
job = run("agorismewiki")
check("it says how long to wait when the site says", "about 49 minutes" in (job["error"] or ""), job)

# ---- the wiki: GitLab first, its own website when GitLab refuses ----
from library import fetch_agorismewiki as wiki  # noqa: E402

site = [{"file": "a.md", "title": "A", "url": "https://agorismewiki.nl/a/", "text": "x"}]
real = wiki.repository_articles, wiki.site_articles
wiki.repository_articles = lambda timeout=120: busy_for_50_minutes()
wiki.site_articles = lambda timeout=120: site
check("GitLab refuses: the website's copy is used", wiki.articles() == site)


def offline(timeout=120):
    raise urllib.error.URLError("no network")


wiki.site_articles = offline
try:
    wiki.articles()
    check("both refuse: GitLab's error (with its wait time) is the one reported", False)
except urllib.error.HTTPError as exc:
    check("both refuse: GitLab's error (with its wait time) is the one reported", exc.code == 429)
wiki.repository_articles = lambda timeout=120: [{"file": "b.md", "title": "B", "url": "u", "text": "y"}]
check("GitLab answers: the website isn't asked", wiki.articles()[0]["title"] == "B")
wiki.repository_articles, wiki.site_articles = real

shutil.rmtree(TMP, ignore_errors=True)
print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
