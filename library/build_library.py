"""Turn the downloaded sources into a plain-text library plus a full-text search index.

Usage: .venv/bin/python library/build_library.py [--public | --lite] [--rebuild KEY ...]
Re-run any time: sources already indexed are skipped, so new downloads just get added.
--rebuild drops the named sources (e.g. wikem) first so they are converted again.
--public builds only what may be redistributed; --lite also leaves out Wikipedia and iFixit.
Set LIBRARY_OUT=DIR to build somewhere other than library.noindex (e.g. a public pack).
Writes library.noindex/text/<source>/NNNN.md (plain-text Markdown shards of about 16 MB)
and library.noindex/index.sqlite (SQLite FTS5 over ~1,500-character passages).
"""
import csv
import fcntl
import glob
import hashlib
import json
import multiprocessing as mp
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from library.passages import split_passages  # noqa: E402

SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library.noindex"))
LIB = os.path.abspath(os.environ.get("LIBRARY_OUT", SRC))  # where the text and index go
ZIM_DIR = os.path.join(SRC, "zim")
RAW_DIR = os.path.join(SRC, "raw")
TEXT_DIR = os.path.join(LIB, "text")
DB_PATH = os.path.join(LIB, "index.sqlite")
WIKIHOW_CSV = os.path.join(RAW_DIR, "wikihowAll.csv")
ARGS = sys.argv[1:]
PUBLIC = "--public" in ARGS  # only what we may redistribute (see SOURCES.md)
LITE = "--lite" in ARGS      # public, minus the big general-reference sources
NOT_PUBLIC = {"post-disaster", "water", "food-prep", "medical-library", "knots"}
NOT_LITE = {"wikipedia", "ifixit"}
SHARD_BYTES = 16 * 1024 * 1024
MIN_CHARS = 300

# ZIM file name (minus the date) -> (key, label shown to the model, topic, kind, URL prefix)
ZIM_SOURCES = {
    "wikipedia_en_top1m_nopic": ("wikipedia", "Wikipedia", "encyclopedia", "wiki", "https://en.wikipedia.org/wiki/"),
    "wikipedia_en_medicine_nopic": ("wikimed", "WikiMed (Wikipedia medicine)", "medical", "wiki", "https://en.wikipedia.org/wiki/"),
    "wikem_en_all_nopic": ("wikem", "WikEM emergency medicine", "medical", "wiki", "https://wikem.org/wiki/"),
    "appropedia_en_all_maxi": ("appropedia", "Appropedia", "howto", "wiki", "https://www.appropedia.org/"),
    "medlineplus.gov_en_all": ("medlineplus", "MedlinePlus (NIH)", "medical", "web", "https://"),
    "nhs.uk_en_medicines": ("nhs-medicines", "UK Medicines A to Z (public sector information)", "medical", "web",
                            "https://"),
    "wwwnc.cdc.gov_en_all": ("cdc-travel", "CDC Travelers' Health", "medical", "web", "https://"),
    "ready.gov_en_all": ("ready-gov", "Ready.gov (FEMA)", "emergency", "web", "https://"),
    "ifixit_en_all": ("ifixit", "iFixit repair guides", "repair", "web", "https://www.ifixit.com/"),
    "irp.fas.org_en_military-medicine": ("military-medicine", "Military medicine manuals", "medical", "pdf",
                                         "https://"),
    "zimgit-medicine_en": ("medical-library", "Medical Library", "medical", "pdf", ""),
    "zimgit-post-disaster_en": ("post-disaster", "Post Disaster Resource Library", "emergency", "pdf", ""),
    "zimgit-water_en": ("water", "Water Treatment Library", "emergency", "pdf", ""),
    "zimgit-food-preparation_en": ("food-prep", "Food for Preppers", "emergency", "pdf", ""),
    "zimgit-knots_en": ("knots", "Library of Knots", "howto", "pdf", ""),
    "usda-2015_en": ("usda-canning", "USDA Complete Guide to Home Canning", "emergency", "web", ""),
    "wikiciv_en_all_maxi": ("wikiciv", "WikiCiv (rebuilding technology)", "howto", "wiki", "https://wikiciv.org/wiki/"),
    "gardenology.org_en_all": ("gardenology", "Gardenology plant encyclopedia", "howto", "wiki", "https://"),
    "energypedia_en_all_nopic": ("energypedia", "Energypedia (solar, batteries, stoves)", "howto", "wiki",
                                 "https://energypedia.info/wiki/"),
}
# Standalone PDF manuals from library/fetch_manuals.py: key -> (label, topic, folder under raw/)
PDF_SOURCES = {
    "survival-manuals": ("U.S. government survival and first-aid manuals", "emergency", "manuals/us-gov"),
    "first-aid-guides": ("IFRC and WHO first-aid and emergency care guides", "medical", "manuals/nc"),
    "risk": ("Risk and micromort references", "medical", "risk"),  # from library/fetch_risk.py
}
SE_SITES = {
    "diy": ("Home Improvement Q&A", "repair"),
    "outdoors": ("The Great Outdoors Q&A", "howto"),
    "cooking": ("Cooking Q&A", "howto"),
    "gardening": ("Gardening Q&A", "howto"),
    "lifehacks": ("Lifehacks Q&A", "howto"),
    "sustainability": ("Sustainable Living Q&A", "howto"),
    "ham": ("Amateur Radio Q&A", "howto"),
    "medicalsciences": ("Medical Sciences Q&A", "medical"),
    "mechanics": ("Motor Vehicle Repair Q&A", "repair"),
    "pets": ("Pets Q&A", "howto"),
}
for site, (label, topic) in SE_SITES.items():
    ZIM_SOURCES[f"{site}.stackexchange.com_en_all"] = (
        f"se-{site}", f"{label} (Stack Exchange)", topic, "se", f"https://{site}.stackexchange.com/")

WIKI_FAMILY = {"wikipedia", "wikimed"}  # same articles can appear in both; keep one copy

# Each source's license, shown with its articles in the app (CC licenses ask for the license with every copy).
CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/"
CC_BY_NC_SA = "https://creativecommons.org/licenses/by-nc-sa/3.0/"
US_GOV = "Public domain (U.S. government work)"
LICENSES = {
    "wikipedia": f"CC BY-SA 4.0, Wikipedia contributors {CC_BY_SA}",
    "wikimed": f"CC BY-SA 4.0, Wikipedia contributors {CC_BY_SA}",
    "wikem": f"CC BY-SA 4.0, WikEM contributors {CC_BY_SA}",
    "appropedia": f"CC BY-SA 3.0 or 4.0 (per page), Appropedia contributors {CC_BY_SA}",
    "energypedia": f"CC BY-SA 3.0 or 4.0 (per page), Energypedia contributors {CC_BY_SA}",
    "wikiciv": f"CC BY-SA 4.0, WikiCiv contributors {CC_BY_SA}",
    "medlineplus": f"{US_GOV}, U.S. National Library of Medicine",
    "nhs-medicines": "Contains public sector information licensed under the Open Government Licence v3.0 "
                     "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    "cdc-travel": f"{US_GOV}, CDC (the printed Yellow Book is published by Oxford University Press)",
    "ready-gov": f"{US_GOV}, FEMA",
    "military-medicine": US_GOV,
    "usda-canning": f"{US_GOV}, USDA",
    "ifixit": f"CC BY-NC-SA 3.0 (non-commercial), iFixit guide authors {CC_BY_NC_SA}",
    "wikihow": f"CC BY-NC-SA 3.0 (non-commercial), wikiHow contributors {CC_BY_NC_SA}",
    "survival-manuals": f"{US_GOV}, except Nuclear War Survival Skills (1986 additions copyright Cresson H. Kearny, "
                        "reproduced with his notice) and the Emergency Response Guidebook 2024 (reproduction "
                        "permitted by the participating governments, not for resale)",
    "risk": f"U.S. government statistics (SSA, CDC, NHTSA, NWS): public domain. Wikipedia articles: {CC_BY_SA}",
    "first-aid-guides": "IFRC guidelines: non-commercial use with acknowledgement. WHO publications: CC BY-NC-SA 3.0 IGO "
                        "https://creativecommons.org/licenses/by-nc-sa/3.0/igo/ (WHO does not endorse this app)",
    **{f"se-{site}": "CC BY-SA 2.5, 3.0 or 4.0 by post date, the authors named with each post "
                     "https://stackoverflow.com/help/licensing" for site in SE_SITES},
}
# PDFs inside ZIMs that are only named by file: give them their real titles.
MILMED = "irp.fas.org/doddir/milmed/"
USDA = "files/GUIDE0{}_HomeCan_rev0715.pdf"
PDF_TITLES = {
    MILMED + "corpsman-pt1.pdf": "Hospital Corpsman (NAVEDTRA 14295), part 1",
    MILMED + "corpsman-pt2.pdf": "Hospital Corpsman (NAVEDTRA 14295), part 2",
    MILMED + "corpsman-pt3.pdf": "Hospital Corpsman (NAVEDTRA 14295), part 3",
    MILMED + "dosimetry.pdf": "Personnel Dosimetry Guidance (DA Pam 40-18)",
    MILMED + "duequip.pdf": "Handling Equipment Contaminated with Depleted Uranium (DA Pam 700-48)",
    MILMED + "first.pdf": "First Aid (FM 4-25.11)",
    MILMED + "malaria.pdf": "Navy Pocket Guide to Malaria Prevention and Control",
    MILMED + "milderm.pdf": "Military Dermatology (Textbook of Military Medicine)",
    MILMED + "preventive.pdf": "Preventive Medicine (DA Pam 40-11)",
    MILMED + "prevserv.pdf": "Preventive Medicine Services (FM 4-02.17)",
    MILMED + "rhpm.pdf": "Radiation Health Protection Manual (NAVMED P-5055)",
    MILMED + "sanitation.pdf": "Unit Field Sanitation Team (FM 4-25.12)",
    MILMED + "ships.pdf": "The Ship's Medicine Chest and Medical Aid at Sea",
    MILMED + "soldiers.pdf": "First Aid for Soldiers (FM 21-11, 1988)",
    MILMED + "sterile.pdf": "Sterilizing Medical, Surgical and Dental Equipment (Army technical bulletin)",
    MILMED + "surghand.pdf": "Division and Brigade Surgeons' Handbook (FM 4-02.21)",
    MILMED + "warpsychiatry.pdf": "War Psychiatry (Textbook of Military Medicine)",
    "files/INTRO_HomeCanrev0715.pdf": "USDA Complete Guide to Home Canning: Introduction",
    USDA.format(1): "USDA Home Canning Guide 1: Principles of Home Canning",
    USDA.format(2): "USDA Home Canning Guide 2: Selecting, Preparing, and Canning Fruit and Fruit Products",
    USDA.format(3): "USDA Home Canning Guide 3: Selecting, Preparing, and Canning Tomatoes and Tomato Products",
    USDA.format(4): "USDA Home Canning Guide 4: Selecting, Preparing, and Canning Vegetables and Vegetable Products",
    USDA.format(5): "USDA Home Canning Guide 5: Preparing and Canning Poultry, Red Meats, and Seafoods",
    USDA.format(6): "USDA Home Canning Guide 6: Preparing and Canning Fermented Foods and Pickled Vegetables",
    USDA.format(7): "USDA Home Canning Guide 7: Preparing and Canning Jams and Jellies",
}
# Sources whose files carry no usable web address: every article links to where the source is published.
FIXED_URLS = {"usda-canning": "https://nchfp.uga.edu/resources/category/usda-guide"}

# Page paths to leave out: WikEM's translated copies ("Page/tr") and sites' non-English sections, including
# language-code sections at the top of a site ("www.ready.gov/fr/..."), which often hold untranslated English copies.
FOREIGN_SECTIONS = r"^[^/]+/[a-z]{2}(-[a-z]+)?/|/(es|spanish|espanol|languages|translations)(/|$)"
SKIP_PATHS = {
    "wikem": r"/[a-z]{2}(-[a-z]+)?$",
    "medlineplus": FOREIGN_SECTIONS,
    "ready-gov": FOREIGN_SECTIONS,
    "cdc-travel": FOREIGN_SECTIONS,
}
if PUBLIC or LITE:  # MedlinePlus sections that third parties license to NLM (A.D.A.M., ASHP, Natural Medicines)
    SKIP_PATHS["medlineplus"] = r"/(ency|druginfo)/|" + FOREIGN_SECTIONS
    # Military volumes that reprint copyrighted figures and text ("certain parts ... copyright restrictions").
    SKIP_PATHS["military-medicine"] = r"/(milderm|warpsychiatry|soldiers)\.pdf$"

HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "#### ", "h6": "#### "}
BLOCKS = {"p", "div", "section", "article", "ul", "ol", "dl", "dt", "dd", "table", "pre", "blockquote",
          "figure", "figcaption", "details", "summary", "main", "center", "hr", "caption"}
DROP_XPATH = (".//script|.//style|.//noscript|.//template|.//svg|.//button|.//form|.//nav|.//footer|.//header"
              "|.//aside|.//sup[contains(@class,'reference')]")
DROP_CLASS = re.compile(
    r"\b(mw-editsection|references|mw-references-wrap|reflist|navbox|vertical-navbox|sidebar|metadata|ambox"
    r"|noprint|catlinks|zim-footer|mw-empty-elt|printfooter|mw-jump-link|toc|mw-cite-backlink|comments"
    r"|js-post-comments-component|credit-author-team-container)\b")
DROP_SECTIONS = {"references", "external links", "see also", "further reading", "notes", "sources",
                 "bibliography", "citations", "footnotes", "notes and references", "references and notes"}
TITLE_SUFFIX = re.compile(
    r"\s*[|:\-–—]\s*(NHS|Ready\.gov|FEMA|CDC|Travelers' Health|MedlinePlus[^|]*|iFixit[^|]*|Appropedia[^|]*"
    r"|Wikipedia|WikEM)\s*$", re.I)


# ---------- HTML / PDF to plain text ----------

def heading_level(el):
    return int(el.tag[1]) if isinstance(el.tag, str) and el.tag in HEADINGS else None


def drop_sections(node):
    """Remove References / External links / See also sections, whatever the markup style."""
    for h in node.xpath(".//h2|.//h3|.//h4"):
        if h.getparent() is None or " ".join(h.text_content().split()).lower() not in DROP_SECTIONS:
            continue
        anchor = h
        parent = h.getparent()
        if parent.tag == "div" and "mw-heading" in (parent.get("class") or ""):
            anchor = parent  # MediaWiki 1.43+ wraps headings in <div class="mw-heading">
        wrapper = anchor.getparent()
        if wrapper is not None and wrapper.tag in ("section", "details") and len(wrapper) and wrapper[0] is anchor:
            wrapper.drop_tree()
            continue
        if wrapper is not None and wrapper.tag == "summary":
            wrapper.getparent().drop_tree()
            continue
        level = int(h.tag[1])
        sib = anchor.getnext()
        anchor.drop_tree()
        while sib is not None:
            inner = sib if heading_level(sib) else (sib[0] if len(sib) and heading_level(sib[0]) else None)
            if inner is not None and heading_level(inner) <= level:
                break
            nxt = sib.getnext()
            sib.drop_tree()
            sib = nxt


def node_text(node):
    """Element tree to plain text, keeping headings, numbered steps, bullets and table rows."""
    for bad in node.xpath(DROP_XPATH):
        bad.drop_tree()
    for el in node.xpath(".//*[@class]"):
        if DROP_CLASS.search(el.get("class")):
            el.drop_tree()
    for ol in node.iter("ol"):
        for n, li in enumerate((c for c in ol if c.tag == "li"), 1):
            li.set("data-n", str(n))
    for el in node.iter():
        if not isinstance(el.tag, str):
            continue
        t = el.tag
        if t in HEADINGS:
            el.text = "\n\n" + HEADINGS[t] + (el.text or "")
            el.tail = "\n\n" + (el.tail or "")
        elif t == "li":
            el.text = (f"\n{el.get('data-n')}. " if el.get("data-n") else "\n- ") + (el.text or "")
        elif t == "tr":
            el.text = "\n" + (el.text or "")
        elif t in ("td", "th"):
            el.tail = " | " + (el.tail or "")
        elif t == "br":
            el.tail = "\n" + (el.tail or "")
        elif t in BLOCKS:
            el.text = "\n\n" + (el.text or "")
            el.tail = "\n\n" + (el.tail or "")
    lines = []
    for line in node.text_content().split("\n"):
        line = re.sub(r"[ \t ​]+", " ", line).strip()
        line = re.sub(r"(\s*\|)+\s*$", "", line)
        if line in ("-", "#", "##", "###", "####") or re.fullmatch(r"\d+\.", line):
            line = ""
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def clean_title(title):
    return TITLE_SUFFIX.sub("", " ".join(title.split())).strip()


def html_to_text(html, kind):
    import lxml.html
    doc = lxml.html.fromstring(html)
    if kind == "se":
        q = doc.xpath("//div[@id='question']")
        if not q:
            return None
        body = q[0].xpath(".//div[contains(@class,'js-post-body')]")
        answers = []
        for a in doc.xpath("//div[contains(concat(' ', @class, ' '), ' answer ')][@data-score]"):
            a_body = a.xpath(".//div[contains(@class,'js-post-body')]")
            if a_body:
                accepted = "accepted-answer" in (a.get("class") or "")
                answers.append((int(a.get("data-score") or 0), accepted, a_body[0]))
        if not body or not answers:
            return None  # unanswered questions are not worth the space
        answers.sort(key=lambda x: (not x[1], -x[0]))
        parts = [f"Question{se_author(q[0], question=True)} (score {q[0].get('data-score', '0')}):\n\n"
                 + node_text(body[0])]
        for score, accepted, a_body in answers[:5]:
            if score < 0:
                continue
            post = a_body.xpath("ancestor::div[@data-score][1]")
            by = se_author(post[0]) if post else ""
            parts.append(f"## Answer{by} (score {score}{', accepted' if accepted else ''})\n\n" + node_text(a_body))
        return "\n\n".join(parts)
    if kind == "wiki":
        found = doc.xpath("//*[@id='mw-content-text']") or doc.xpath("//*[contains(@class,'mw-parser-output')]")
        if found:  # otherwise (e.g. a scraped wiki) fall through to the general page extraction
            node = found[0]
            drop_sections(node)
            return node_text(node)
    # Scraped websites: take <main> or <article>; fall back to trafilatura's boilerplate removal.
    author = doc.xpath("//div[contains(@class,'guide-author')]")  # iFixit: "Written By: <name>"
    author = " ".join(author[0].text_content().split()) if author else ""
    found = doc.xpath("//main") or doc.xpath("//article") or doc.xpath("//*[@id='content']")
    text = node_text(found[0]) if found else ""
    if author and text:
        text = f"{author}\n\n{text}"
    if len(text) < MIN_CHARS:
        import trafilatura
        text = trafilatura.extract(html, include_tables=True, include_comments=False) or ""
    return text


def se_author(post, question=False):
    """ ' by <name>' for a Stack Exchange post (its license asks for the author's name), or ''."""
    sigs = post.xpath(".//div[contains(@class,'post-signature')]")
    if question:
        sigs = [s for s in sigs if "owner" in (s.get("class") or "")] or sigs
    name = sigs[-1].xpath(".//*[contains(@class,'s-user-card--link')]") if sigs else []
    name = " ".join(name[0].text_content().split()) if name else ""
    return f" by {name}" if name else ""


def pdf_to_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        r = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", f.name, "-"], capture_output=True, timeout=600)
    text = r.stdout.decode("utf-8", "replace").replace("\f", "\n\n")
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    return "\n\n".join(p for p in paras if p)


# ---------- ZIM workers ----------

_ARCHIVE = None
_KIND = None
_SKIP = None


def _init_worker(path, kind, skip=None):
    global _ARCHIVE, _KIND, _SKIP
    from libzim.reader import Archive
    os.nice(10)
    _ARCHIVE = Archive(path)
    _KIND = kind
    _SKIP = re.compile(skip) if skip else None


def _convert_range(bounds):
    out = []
    for i in range(*bounds):
        try:
            e = _ARCHIVE._get_entry_by_id(i)
            if e.is_redirect or (_SKIP and _SKIP.search(e.path)) or re.match(r"(?i)h?ttps?:", e.path):
                continue
            item = e.get_item()
            mime = item.mimetype.split(";")[0]
            if mime == "application/pdf" and _KIND in ("pdf", "web"):
                text = pdf_to_text(bytes(item.content))
                title = e.title if e.title and e.title != e.path else os.path.basename(e.path)
                title = re.sub(r"\.pdf$", "", title.replace("_", " "), flags=re.I)
                title = PDF_TITLES.get(e.path, title)
                if re.search(r"\(\d+\)$", title):  # zimgit names files "Water (7)"; lead with the PDF's first line
                    first = next((p for p in text.split("\n\n") if len(p) >= 12), "")
                    if first:
                        title = (first[:80].rsplit(" ", 1)[0] if len(first) > 80 else first) + f" [{title}]"
            elif mime == "text/html":
                if _KIND == "se" and not e.path.startswith("questions/"):
                    continue
                text = html_to_text(bytes(item.content), _KIND)
                title = e.title or e.path
            else:
                continue
            if text and len(text) >= MIN_CHARS:
                out.append((clean_title(title), e.path, text))
        except Exception as exc:  # one bad page must not stop a million-page build
            print(f"    skipped entry {i}: {exc}", file=sys.stderr)
    return out


def reused_docs(key, origin, url_prefix, skip=None):
    """A pack build reuses text the personal library already converted from the same file, instead of
    converting it again (Wikipedia takes most of an hour). Returns None when there is nothing to reuse."""
    index = os.path.join(SRC, "index.sqlite")
    if LIB == SRC or not os.path.exists(index):
        return None
    src = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    row = src.execute("SELECT id FROM sources WHERE key=? AND origin=? AND done=1",
                      (key, os.path.basename(origin))).fetchone()
    if not row:
        src.close()
        return None
    rx = re.compile(skip) if skip else None

    def docs():
        rel, fh = None, None
        for title, url, path, offset, length in src.execute(
                "SELECT d.title, d.url, f.path, d.offset, d.length FROM docs d JOIN files f ON f.id = d.file_id "
                "WHERE d.source_id=? ORDER BY d.id", row):
            if rx and rx.search(url[len(url_prefix):] if url_prefix and url.startswith(url_prefix) else url):
                continue
            if path != rel:
                if fh:
                    fh.close()
                rel, fh = path, open(os.path.join(SRC, "text", path), "rb")
            fh.seek(offset)
            text = fh.read(length).decode("utf-8")
            yield title, url, text.split("\n\n", 1)[1].rsplit("---", 1)[0]  # drop the header and the divider
        if fh:
            fh.close()
        src.close()
    return docs()


def zim_docs(path, kind, skip=None):
    from libzim.reader import Archive
    count = Archive(path).entry_count
    step = 50 if kind == "pdf" else 1000
    ranges = [(s, min(s + step, count)) for s in range(0, count, step)]
    with mp.Pool(10, initializer=_init_worker, initargs=(path, kind, skip)) as pool:
        for batch in pool.imap(_convert_range, ranges):
            yield from batch


def manual_docs(folder):
    """Files listed in folder/manifest.json (written by fetch_manuals.py or fetch_risk.py): PDFs, web pages, text.
    Copies of Wikipedia articles are skipped when the build has Wikipedia itself."""
    with open(os.path.join(folder, "manifest.json")) as f:
        items = json.load(f)
    for item in items:
        if item.get("wikipedia") and wanted("wikipedia"):
            continue
        with open(os.path.join(folder, item["file"]), "rb") as f:
            data = f.read()
        if item["file"].endswith(".pdf"):
            text = pdf_to_text(data)
        elif item["file"].endswith((".html", ".htm")):
            text = html_to_text(data, item.get("kind", "web")) or ""
        else:
            text = data.decode("utf-8", "replace")
        if len(text) >= MIN_CHARS:
            yield item["title"], item["url"], text
        else:
            print(f"    no text layer (needs OCR): {item['title']}", flush=True)


def wikihow_docs(path):
    csv.field_size_limit(sys.maxsize)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # The dump glues a counter onto titles ("How to Be an Organized Artist1").
            title = re.sub(r"(?<=[A-Za-z)])\d+$", "", (row.get("title") or "").strip()).strip()
            heads = [h.strip().rstrip(",").strip() for h in (row.get("headline") or "").split("\n")]
            heads = [h for h in heads if h]
            paras = [" ".join(p.split()) for p in re.split(r";?\n,", row.get("text") or "")]
            paras = [p.strip(" ;,") for p in paras if p.strip(" ;,")]
            if not title or not paras:
                continue
            if len(heads) == len(paras):
                steps = [f"{n}. {h}\n\n{p}" for n, (h, p) in enumerate(zip(heads, paras), 1)]
            else:
                steps = ["## Steps\n\n" + "\n".join(f"{n}. {h}" for n, h in enumerate(heads, 1))] if heads else []
                steps += ["## Details"] + paras
            text = "\n\n".join(steps)
            if len(text) >= MIN_CHARS:
                yield title, "https://www.wikihow.com/" + title.replace("How to ", "").replace(" ", "-"), text


# ---------- writing shards and the index ----------

class SourceWriter:
    def __init__(self, db, source_id, key, label):
        self.db, self.source_id, self.label = db, source_id, label
        self.dir = os.path.join(TEXT_DIR, key)
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        self.key, self.shard, self.f, self.pos, self.file_id, self.docs = key, -1, None, 0, None, 0

    def _next_shard(self):
        if self.f:
            self.f.close()
        self.shard += 1
        rel = f"{self.key}/{self.shard:04d}.md"
        self.f = open(os.path.join(TEXT_DIR, rel), "wb")
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


def open_db():
    db = sqlite3.connect(DB_PATH, isolation_level=None)
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


ONLY = set(ARGS[ARGS.index("--only") + 1].split(",")) if "--only" in ARGS else None  # e.g. for test packs


def wanted(key):
    if ONLY is not None and key not in ONLY:
        return False
    if (PUBLIC or LITE) and key in NOT_PUBLIC:
        return False
    return not (LITE and key in NOT_LITE)


def build_source(db, key, label, topic, origin, docs_iter):
    if not wanted(key):
        return False
    row = db.execute("SELECT done FROM sources WHERE key=?", (key,)).fetchone()
    if row and row[0]:
        return False
    start = time.time()
    print(f"building {key} from {os.path.basename(origin)}", flush=True)
    seen_titles = set()
    if key in WIKI_FAMILY:
        seen_titles = {t.lower() for (t,) in db.execute(
            "SELECT d.title FROM docs d JOIN sources s ON s.id = d.source_id WHERE s.key IN (%s)"
            % ",".join("?" * len(WIKI_FAMILY)), sorted(WIKI_FAMILY))}
    db.execute("BEGIN")
    try:
        db.execute("DELETE FROM sources WHERE key=?", (key,))  # leftover from an interrupted run
        source_id = db.execute("INSERT INTO sources(key, label, topic, origin) VALUES(?,?,?,?)",
                               (key, label, topic, os.path.basename(origin))).lastrowid
        writer = SourceWriter(db, source_id, key, label)
        copies = set()  # sites serve some pages at several addresses (CDC's Yellow Book under every country)
        for title, url, text in docs_iter:
            if seen_titles and title.lower() in seen_titles:
                continue
            digest = hashlib.blake2b(f"{title}\n{text}".encode(), digest_size=16).digest()
            if digest in copies:
                continue
            copies.add(digest)
            writer.add(title, url, text)
            if writer.docs % 20000 == 0:
                print(f"    {writer.docs:,} articles, {time.time() - start:.0f}s", flush=True)
        writer.close()
        db.execute("UPDATE sources SET docs=?, done=1 WHERE id=?", (writer.docs, source_id))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    print(f"    done: {writer.docs:,} articles in {time.time() - start:.0f}s", flush=True)
    return True


def drop_source(db, key):
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
    shutil.rmtree(os.path.join(TEXT_DIR, key), ignore_errors=True)
    print(f"dropped {key}", flush=True)


def main():
    os.makedirs(TEXT_DIR, exist_ok=True)
    print(f"building into {LIB}" + (" (lite public pack)" if LITE else " (public pack)" if PUBLIC else ""), flush=True)
    lock = open(os.path.join(LIB, ".build.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another build is already running")
    db = open_db()
    if sys.argv[1:2] == ["--rebuild"]:  # e.g. --rebuild wikem cdc-travel
        for key in sys.argv[2:]:
            drop_source(db, key)
    changed = False
    if os.path.exists(WIKIHOW_CSV):
        changed |= build_source(db, "wikihow", "wikiHow", "howto", WIKIHOW_CSV, wikihow_docs(WIKIHOW_CSV))
    for key, (label, topic, sub) in PDF_SOURCES.items():
        folder = os.path.join(RAW_DIR, sub)
        if os.path.exists(os.path.join(folder, "manifest.json")):
            changed |= build_source(db, key, label, topic, folder, manual_docs(folder))
    # WikiMed before Wikipedia so medical articles keep WikiMed as their source.
    order = sorted(ZIM_SOURCES, key=lambda k: (k != "wikipedia_en_medicine_nopic", k == "wikipedia_en_top1m_nopic"))
    for prefix in order:
        key, label, topic, kind, url_prefix = ZIM_SOURCES[prefix]
        files = sorted(f for f in glob.glob(os.path.join(ZIM_DIR, prefix + "_*.zim")) if os.path.exists(f + ".done"))
        if not files:
            continue
        path = files[-1]
        docs = reused_docs(key, path, url_prefix, SKIP_PATHS.get(key)) if wanted(key) else None
        if docs is None:
            docs = ((t, FIXED_URLS.get(key) or (url_prefix + p if url_prefix else p), x)
                    for t, p, x in zim_docs(path, kind, SKIP_PATHS.get(key)))
        changed |= build_source(db, key, label, topic, path, docs)
    for key, text in LICENSES.items():
        db.execute("UPDATE sources SET license=? WHERE key=?", (text, key))
    if changed:
        print("optimizing index", flush=True)
        db.execute("INSERT INTO fts(fts) VALUES('optimize')")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    if sys.argv[1:2] == ["--rebuild"]:  # the dropped sources' pages stay in the file, and in a pack's zip, until this
        print("compacting index", flush=True)
        db.execute("VACUUM")
    try:  # one self-contained file, so read-only copies (packs, read-only disks) open cleanly
        db.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass  # the app has it open; it stays in WAL mode until the next build
    total = db.execute("SELECT COUNT(*), COALESCE(SUM(docs), 0) FROM sources WHERE done=1").fetchone()
    print(f"library: {total[1]:,} articles from {total[0]} sources", flush=True)


if __name__ == "__main__":
    main()
