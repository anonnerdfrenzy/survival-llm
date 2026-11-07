"""The app's languages come from one table (core.LANGUAGES): the Language menu, the interface packs the page loads,
the computer's own language, and the "Sources" line in every language. A made-up third language shows that adding
one needs no other code.

Usage: python3 tests/languages_test.py"""
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="languages-test-")
os.environ.update(SURVIVAL_LLM_APP_DIR=os.path.join(TMP, "settings"), SURVIVAL_LLM_FILES=os.path.join(TMP, "files"),
                  SURVIVAL_LLM_LIBRARY=os.path.join(TMP, "library"), OLLAMA_HOST="127.0.0.1:9")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, ROOT)
import core  # noqa: E402
import server  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail!r}"))
    if not ok:
        FAILS.append(name)


# ---- every language is complete ----
for code in core.LANGUAGES:
    check(f"{code}: has AI instructions and Sources words", code in core.LANGUAGE_PROMPTS and code in core.SOURCES_WORDS)
    if code != "en":
        check(f"{code}: has its interface pack", os.path.isfile(os.path.join(server.STATIC, f"lang-{code}.js")))
check("menu lists English and Dutch, each in its own language",
      'value="en"' in server.language_options() and ">Nederlands<" in server.language_options())
check("the page loads the Dutch pack", server.language_scripts() == '<script src="/static/lang-nl.js"></script>')

# ---- the computer's language ----
for env, want in [({"LANG": "nl_NL.UTF-8"}, "nl"), ({"LANG": "nl_BE.UTF-8"}, "nl"), ({"LANG": "en_GB.UTF-8"}, "en"),
                  ({"LANG": "fr_FR.UTF-8"}, "en"), ({"LC_ALL": "C", "LANG": "nl_NL"}, "nl")]:
    saved = {k: os.environ.pop(k, None) for k in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")}
    os.environ.update(env)
    got = server.system_language()
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v
    check(f"computer set to {env} speaks {want}", got == want, got)

# ---- a made-up third language ----
core.LANGUAGES["de"] = {"name": "Deutsch", "english": "German"}
core.LANGUAGE_PROMPTS["de"] = "Language: the person speaks German. Always answer in German."
core.SOURCES_WORDS["de"] = {"words": ["Quellen", "Quelle"], "head": "Quellen: ", "none_opened": "Quellen: keine",
                            "earlier": "Quellen: früher", "none": "Quellen: keine (eigenes Wissen)"}
saved = os.environ.get("LANG")
os.environ["LANG"] = "de_DE.UTF-8"
check("a new language is the computer's language", server.system_language() == "de")
os.environ["LANG"] = saved or ""
check("but not in the menu without its pack", ">Deutsch<" not in server.language_options())
core.LANGUAGES.pop("de"), core.LANGUAGE_PROMPTS.pop("de"), core.SOURCES_WORDS.pop("de")

# ---- the Sources line is read in every language the table lists ----
words = [w for v in core.SOURCES_WORDS.values() for w in v["words"]]
check("the Sources pattern holds every language's words", all(w in core.SOURCE_WORD for w in words), core.SOURCE_WORD)
for v in core.SOURCES_WORDS.values():
    plural = v["words"][0]
    check(f"a {plural} list is read", core.cited_sources(f"Answer.\n\n{plural}: A; B") == ["A", "B"])

pack = os.path.join(server.STATIC, "lang-de.js")
try:
    open(pack, "w").close()
    server.core.LANGUAGES["de"] = {"name": "Deutsch", "english": "German"}
    check("with its pack it is in the menu and loaded", ">Deutsch<" in server.language_options()
          and "lang-de.js" in server.language_scripts())
finally:
    os.remove(pack)
    server.core.LANGUAGES.pop("de", None)

print(f"{len(FAILS)} failed" if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
