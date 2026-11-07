"""Download the Dutch Agorisme wiki (agorismewiki.nl) into library.noindex/raw/agorismewiki/.

Usage: python3 library/fetch_agorismewiki.py             download it, for build_library.py
       python3 library/fetch_agorismewiki.py --install   download it and add it to the library the app uses
                                                          (close the app first; run it again after a library update,
                                                          which replaces the library folder)
The site is built with Zola from Markdown in a public GitLab repository, so this takes the articles from there
(one download of the repository, no scraping). It writes one text file per article, plus one for the glossary
(data/glossary.toml, the site's /termen/ page), and manifest.json for build_library.py. Zola's markup is turned
into plain Markdown: internal links (@/page.md) become web addresses, the "warning" boxes become "Let op" lines,
and images keep only their description. The site states no license (checked 2026-11-07), so build_library.py
leaves this source out of the --public and --lite packs: personal builds only, until the authors give permission.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library.noindex")
OUT = os.path.join(ROOT, "raw", "agorismewiki")
ARCHIVE = "https://gitlab.com/softwarehuis/agorisme/-/archive/master/agorisme-master.tar.gz"
# The same archive through GitLab's API: tried when the first address refuses (GitLab limits archive downloads)
ARCHIVE_API = "https://gitlab.com/api/v4/projects/softwarehuis%2Fagorisme/repository/archive.tar.gz?sha=master"
SITE = "https://agorismewiki.nl/"
# The website's own search file: every article's text, as plain lines (no headings, lists or glossary). Used when
# GitLab refuses, which it does after a few downloads an hour from one internet address without a GitLab account.
SITE_INDEX = SITE + "search_index.nl.json"
SITE_SKIP = {"/zoeken/", "/termen/", "/huisregels/"}
SKIP = {"zoeken.md", "termen.md", "huisregels.md"}  # search page, glossary stub (built below), the site's house rules


def front_matter(text):
    """(title, body) of a Zola page with YAML ("---") or TOML ("+++") front matter."""
    m = re.match(r"\A(---|\+\+\+)\s*\n(.*?)\n\1\s*\n", text, re.S)
    if not m:
        return None, text
    title = re.search(r"""^title\s*[:=]\s*["']?(.*?)["']?\s*$""", m.group(2), re.M)
    return (title.group(1).strip() if title else None), text[m.end():]


def page_url(name):
    """The site address of a content file: content/voedsel-bewaren.md is /voedsel-bewaren/."""
    name = name.removesuffix(".md")
    if name in ("_index", ""):
        return SITE
    return SITE + name.removesuffix("/_index").removesuffix("/index") + "/"


def plain(body):
    """Zola Markdown to plain Markdown the library can index and the app can show."""
    body = re.sub(r"\{%\s*warning\(title=\"([^\"]*)\"\)\s*%\}", r"**Let op: \1**", body)
    body = re.sub(r"\{%\s*end\s*%\}", "", body)
    body = re.sub(r"\{[{%].*?[%}]\}", "", body, flags=re.S)  # any other shortcode
    body = re.sub(r"\]\(@/([^)#]+?)(#[^)]*)?\)", lambda m: f"]({page_url(m.group(1))}{m.group(2) or ''})", body)
    body = re.sub(r"!\[([^\]]*)\]\([^)]*\)", lambda m: f"(afbeelding: {m.group(1)})" if m.group(1) else "", body)
    body = re.sub(r"\]\(/(?!/)", "](" + SITE, body)  # root-relative links
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def articles(timeout=120):
    """Download the wiki and return its articles as [{"file", "title", "url", "text"}], sorted by title: from its
    repository on GitLab, else from the website's search file. Nothing is unpacked to disk: it is read in memory.
    Raises GitLab's error (OSError) when neither answers."""
    try:
        return repository_articles(timeout)
    except OSError as exc:
        try:
            return site_articles(timeout)
        except (OSError, ValueError):
            raise exc from None


def site_articles(timeout=120):
    """The articles from the website's search file: one small download, with plain text instead of Markdown."""
    req = urllib.request.Request(SITE_INDEX, headers={"User-Agent": "survival-llm library builder"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        entries = json.load(resp)
    found = []
    for e in entries:
        path = str(e.get("url") or "")
        if path in SITE_SKIP or path.startswith("/categorie"):
            continue
        text = "\n\n".join(line.strip() for line in str(e.get("body") or "").splitlines() if line.strip())
        if not text:
            continue
        title = "Agorisme wiki: welkom" if path == "/" else str(e.get("title") or path.strip("/"))
        found.append({"file": (path.strip("/") or "_index") + ".md", "title": title,
                      "url": SITE + path.lstrip("/"), "text": text})
    return sorted(found, key=lambda a: a["title"].lower())


def repository_articles(timeout=120):
    """The articles from the wiki's repository: its Markdown, with headings, lists and the glossary."""
    data, error = None, None
    for url in (ARCHIVE, ARCHIVE_API):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "survival-llm library builder"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            break
        except OSError as exc:
            error = exc
    if data is None:
        raise error
    found = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if not member.isfile() or len(parts) < 3:
                continue
            rel = "/".join(parts[1:])  # without the archive's top folder
            raw = tar.extractfile(member).read().decode("utf-8", "replace")
            if rel == "data/glossary.toml":
                terms = tomllib.loads(raw).get("terms", [])
                lines = ["Begrippen die op de Agorisme-wiki worden gebruikt, met hun uitleg.", ""]
                for t in terms:
                    also = f" (ook: {', '.join(t['aliases'])})" if t.get("aliases") else ""
                    lines.append(f"**{t.get('term', '').strip()}**{also}: {t.get('definition', '').strip()}\n")
                found.append({"file": "termen.md", "title": "Termen (begrippenlijst)", "url": SITE + "termen/",
                              "text": "\n".join(lines)})
            elif rel.startswith("content/") and rel.endswith(".md") and os.path.basename(rel) not in SKIP:
                name = rel.removeprefix("content/")
                title, body = front_matter(raw)
                text = plain(body)
                if not text:
                    continue
                if name == "_index.md":
                    title = "Agorisme wiki: welkom"
                found.append({"file": re.sub(r"[^\w.-]", "_", name), "title": title or name.removesuffix(".md"),
                              "url": page_url(name), "text": text})
    return sorted(found, key=lambda a: a["title"].lower())


def main():
    print(f"downloading {ARCHIVE}", flush=True)
    found = articles()
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    for a in found:
        with open(os.path.join(OUT, a["file"]), "w", encoding="utf-8") as f:
            f.write(a["text"] + "\n")
    manifest = [{k: a[k] for k in ("file", "title", "url")} for a in found]
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(manifest)} articles in {OUT}", flush=True)
    if not manifest:
        sys.exit("found no articles: has the repository changed?")
    if "--install" in sys.argv[1:]:
        install()


def install():
    """Add (or refresh) this source in the library the app reads, found the way the app finds it."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(here))
    from library import search
    lib = search.LIB
    if not os.path.exists(os.path.join(lib, "index.sqlite")):
        sys.exit(f"No library at {lib} yet. Open Survival LLM, let its setup install the library, close it, and "
                 "run this again.")
    try:  # the app keeps the index open; adding to it then could leave it half-changed
        with open(os.path.join(search.app_dir(), "server.json")) as f:
            port = json.load(f)["port"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=2):
            sys.exit("Survival LLM is running. Close it first, then run this again.")
    except (OSError, ValueError, KeyError):
        pass
    print(f"adding it to the library in {lib}", flush=True)
    build = [sys.executable, os.path.join(here, "build_library.py")]
    env = {**os.environ, "LIBRARY_OUT": lib}
    # --rebuild replaces an older copy; --only leaves every other source alone; --quick skips re-optimizing the
    # whole index (minutes and gigabytes for the full library, for 40 articles)
    subprocess.run(build + ["--rebuild", "agorismewiki", "--only", "agorismewiki", "--quick"], env=env, check=True)


if __name__ == "__main__":
    main()
