"""Checks for the first-run setup (app/server.py): what it downloads next, how it explains a stopped download, that it
tries again on its own and carries on after a restart, that changing the choices stops the download, and that a
library pack really installs from its parts (from files on disk, so no internet).
No Ollama: the model list and the downloads are stand-ins, except the library install at the end.

Usage: .venv/bin/python tests/setup_test.py"""
import errno
import hashlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import zipfile

TMP = tempfile.mkdtemp(prefix="setup-test-")
os.environ.update(SURVIVAL_LLM_APP_DIR=os.path.join(TMP, "settings"), SURVIVAL_LLM_FILES=os.path.join(TMP, "files"),
                  SURVIVAL_LLM_LIBRARY=os.path.join(TMP, "library"), OLLAMA_HOST="127.0.0.1:9")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import server  # noqa: E402

REAL_LIBRARY_WORKER = server.library_worker  # the tests below stand in for it, until the last one
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


def wait_for(test, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if test():
            return True
        time.sleep(0.05)
    return False


# ---------- how a stopped download is explained, and whether trying again can help ----------
cases = [
    (ConnectionResetError("reset by peer"), "network"),
    (urllib.error.URLError(OSError("nodename nor servname provided")), "network"),
    (TimeoutError("timed out"), "network"),
    (http.client.IncompleteRead(b"abc", 10), "network"),
    (OSError(errno.ENOSPC, "No space left on device"), None),
    (urllib.error.HTTPError("https://github.com/x", 503, "busy", {}, io.BytesIO(b"")), "again"),
    (RuntimeError("Part 2 of 5 was damaged in transit. Try again to re-download it."), "again"),
    (RuntimeError("That library pack isn't available. Check the internet connection."), "network"),
    (RuntimeError("Not enough free disk space: installing this pack needs about 27 GB free, and this computer has 9 GB."), None),
    (RuntimeError("Download failed: dial tcp: lookup registry.ollama.ai: no such host"), "network"),
    (RuntimeError("Download failed: pull model manifest: file does not exist"), None),
    (RuntimeError("Download failed: something unexpected"), "again"),
    (__import__("socket").gaierror(8, "nodename nor servname provided"), "network"),
    (OSError(errno.ENETUNREACH, "Network is unreachable"), "network"),
    # the disk, not the internet (review, Oct 28): say so, and don't retry forever
    (PermissionError(13, "Permission denied", "/Volumes/USB/Survival LLM Library.download"), None),
    (OSError(errno.EFBIG, "File too large", "/Volumes/STICK/Survival LLM Library.partial/index.sqlite"), None),
    (OSError(errno.EROFS, "Read-only file system", "/Volumes/CD/x"), None),
]
for exc, want in cases:
    text, retry = server.download_error(exc)
    check(f"{type(exc).__name__} ({str(exc)[:40]}) -> {want}", retry == want and text, (text, retry))
check("a dropped connection reads as plain words", server.download_error(ConnectionResetError("x"))[0]
      == "The internet connection dropped.")
text, _ = server.download_error(OSError(errno.EFBIG, "File too large", "/Volumes/STICK/x"))
check("a FAT32 stick: says so, with the file", "FAT32" in text and "/Volumes/STICK/x" in text, text)
text, _ = server.download_error(PermissionError(13, "Permission denied", "/Volumes/USB/x"))
check("an unplugged or locked drive: says where, not 'internet'", "internet" not in text and "/Volumes/USB/x" in text, text)

# ---------- issue #13: a model that needs a newer AI engine than the Ollama app that is running ----------
too_old = RuntimeError("Download failed: pull model manifest: 412: The model you are attempting to pull requires a newer "
                       "version of Ollama. Please download the latest version at: https://ollama.com/download")
server.own_engine_version = lambda: "0.40.11"
server.running_engine = lambda: {"version": "0.40.9", "ours": False}
text, retry = server.download_error(too_old)
check("#13: their older Ollama app: says quit it to use the app's own engine", "Quit Ollama" in text and "0.40.9" in text
      and "0.40.11" in text and retry is None, text)
server.running_engine = lambda: {"version": "0.41.0", "ours": False}
text, _ = server.download_error(too_old)
check("#13: their Ollama is newer than the app's: says update Ollama", "Update Ollama" in text and "Quit" not in text, text)
server.running_engine = lambda: {"version": "0.40.11", "ours": True}
text, _ = server.download_error(too_old)
check("#13: the app's own engine is too old: says so, not 'update Ollama'", "built into" in text or "installed" in text, text)

# ---------- what setup does next ----------
have = {"pack": None, "models": None, "engine": True}
server.installed_pack = lambda: {"id": have["pack"], "version": "x"} if have["pack"] else None
server.installed_models = lambda: None if have["models"] is None else list(have["models"])
server.ollama_locations = lambda: ("/Applications/Ollama.app", None) if have["engine"] else (None, None)
server.start_ollama = lambda: None
server.library_packs = lambda: [{"id": "lite", "label": "Essentials: medical (1.3 GB)", "gb": 1.3, "parts": []},
                                {"id": "full", "label": "Everything: more (8.8 GB)", "gb": 8.8, "parts": []}]
plan = {"pack": "lite", "model": "granite4.2:8b"}
check("library first", server.setup_step(plan)[:2] == ("library", "library:lite"), server.setup_step(plan))
have["pack"] = "lite"
check("then waits for the AI engine to start", server.setup_step(plan) == ("wait", "engine-starting"), server.setup_step(plan))
have["engine"] = False
server.engine_info = lambda: None
check("no engine and none to download: asks for Ollama", server.setup_step(plan) == ("wait", "install-engine"))
server.engine_info, server.ENGINE = (lambda: {"bytes": 1, "url": "x", "sha256": "x"}), "/tmp/ollama.exe"
check("no engine, one to download (Windows): downloads it", server.setup_step(plan)[:2] == ("engine", "engine"))
have.update(engine=True, models=["gemma4:latest"])
check("then the model", server.setup_step(plan)[:2] == ("model", "model:granite4.2:8b"))
have["models"].append("granite4.2:8b")
check("then nothing", server.setup_step(plan) is None)
check("another pack chosen than the one installed: installs it", server.setup_step({"pack": "full"})[:2]
      == ("library", "library:full"))
check("only an AI chosen", server.setup_step({"pack": None, "model": "gemma4"}) is None)

# ---------- a whole setup: a dropped connection, tried again on its own, then done ----------
server.RETRY_FIRST, server.RETRY_MOST = 0.05, 0.2
awake = []
server.keep_awake = lambda: (awake.append("on"), lambda: awake.append("off"))[1]
calls = {"library": 0, "model": 0}


def fake_library(key, pack_id):
    calls["library"] += 1
    server._update(key, status="downloading", completed=100, total=1000)
    if calls["library"] == 1:
        raise ConnectionResetError("the Wi-Fi went away")
    have["pack"] = pack_id


def fake_pull(key, model):
    calls["model"] += 1
    server._update(key, status="downloading", completed=5, total=10)
    have["models"].append(model)


server.library_worker, server.pull_worker = fake_library, fake_pull
have.update(pack=None, models=[])
server.save_setup({"pack": "lite", "model": "granite4.2:8b"})
runner = threading.Thread(target=server.run_setup, daemon=True)
runner.start()
runner.join(15)
check("setup finished", not runner.is_alive() and server.setup_plan() is None, server.setup_status())
check("the library download was tried again after the dropped connection", calls["library"] == 2, calls)
check("then the model downloaded", calls["model"] == 1 and "granite4.2:8b" in have["models"], calls)
check("kept the computer awake only while downloading (3 downloads), never through the wait between",
      awake == ["on", "off"] * 3, awake)
check("jobs end as done", server.downloads["library:lite"]["status"] == "done"
      and server.downloads["model:granite4.2:8b"]["status"] == "done")
check("status shows no setup once done", server.setup_status() is None)

# ---------- once its library is in, setup forgets the pack (a switch made meanwhile isn't undone) ----------
release = threading.Event()


def slow_pull(key, model):
    release.wait(10)
    have["models"].append(model)


server.library_worker, server.pull_worker = fake_library, slow_pull
calls["library"] = 1  # the fake library succeeds at once from here on
have.update(pack=None, models=[])
server.save_setup({"pack": "lite", "model": "qwen"})
runner = threading.Thread(target=server.run_setup, daemon=True)
runner.start()
check("library in: the plan keeps only the model", wait_for(lambda: server.setup_plan() == {"pack": None, "model": "qwen"}),
      server.setup_plan())
have["pack"] = "full"  # switched to Everything in the Library window while the model downloads
release.set()
runner.join(10)
check("setup ends without reinstalling Essentials over Everything", have["pack"] == "full" and not runner.is_alive())
server.pull_worker = fake_pull

# ---------- quit halfway: the next start carries on ----------
have.update(pack="lite", models=[])
calls.update(library=0, model=0)
server.save_setup({"pack": "lite", "model": "gemma4"})  # left by an app that quit before the model finished
server.run_setup()
check("after a restart it carries on with what's missing", calls == {"library": 0, "model": 1}
      and server.setup_plan() is None, calls)

# ---------- a problem the person has to fix (disk full) waits for Try again ----------
disk = {"full": True}


def full_disk(key, pack_id):
    if disk["full"]:
        raise RuntimeError("Not enough free disk space: installing this pack needs about 27 GB free, and this "
                           "computer has 9 GB.")
    have["pack"] = pack_id


server.library_worker = full_disk
have.update(pack=None, models=["gemma4"])
server.save_setup({"pack": "full", "model": None})
runner = threading.Thread(target=server.run_setup, daemon=True)
runner.start()
check("disk full: waits for the person", wait_for(lambda: (server.setup_status() or {}).get("waiting") == "stuck"),
      server.setup_status())
check("and says why", "Not enough free disk space" in (server.setup_status() or {}).get("error", ""))
time.sleep(0.5)
check("without trying again on its own", runner.is_alive() and server.setup_state["attempts"] == 1, server.setup_state)
disk["full"] = False
server.setup_wake.set()  # Try again
runner.join(10)
check("Try again finishes it", not runner.is_alive() and have["pack"] == "full" and server.setup_plan() is None)

# ---------- changing what to download stops the download ----------
started = threading.Event()


def endless(key, pack_id):
    started.set()
    while True:
        if server.cancels[key].is_set():
            raise server.Cancelled()
        server._update(key, status="downloading", completed=1, total=10)
        time.sleep(0.02)


server.library_worker = endless
have.update(pack=None)
server.save_setup({"pack": "lite", "model": None})
runner = threading.Thread(target=server.run_setup, daemon=True)
runner.start()
started.wait(5)
plan_before = server.setup_plan()
server.clear_setup()  # what /api/setup/cancel does
server.cancels["library:lite"].set()
server.setup_wake.set()
runner.join(5)
check("Change what to download stops it", not runner.is_alive() and server.downloads["library:lite"]["status"]
      == "cancelled" and plan_before, server.downloads["library:lite"])

# ---------- the download speed for "minutes left" ----------
server.downloads["speed"] = {"key": "speed", "status": "downloading", "completed": 0, "total": 0}
server.speeds.pop("speed", None)
server._update("speed", completed=0, total=100)
server.speeds["speed"][0] -= 2  # as if two seconds went by
server._update("speed", completed=4_000_000, total=100)
check("download speed", abs(server.downloads["speed"]["rate"] - 2_000_000) < 20_000, server.downloads["speed"])

# ---------- bin/dev --new-user: models on this computer count as not downloaded until downloaded again ----------
server.HIDDEN.update(on=True, models=None)
check("new user: none of this computer's models show", server.visible_models(["gemma4:latest", "granite4.2:8b"]) == [])
server.HIDDEN["models"].discard("gemma4")  # what downloading it does
check("one downloaded again shows", server.visible_models(["gemma4:latest", "granite4.2:8b"]) == ["gemma4:latest"])
server.HIDDEN.update(on=False, models=None)

# ---------- the setup screen's pack descriptions ----------
real = json.load(open(os.path.join(ROOT, "docs", "library-packs.json")))["packs"]
lite = server.pack_summary(next(p for p in real if p["id"] == "lite"))
check("pack name and contents", lite["name"] == "Essentials" and lite["about"].startswith("Medical, emergency"), lite)
check("pack disk space while installing", lite["disk_gb"] == 5, lite)

# ---------- a real pack install from its parts, leaving no earlier pack's parts behind ----------
src = os.path.join(TMP, "pack-src")
os.makedirs(src)
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("index.sqlite", b"not really a database")
    z.writestr("text/a.md", "# A\n" + "words " * 2000)
data = buf.getvalue()
cut = len(data) // 2
parts = []
for n, chunk in enumerate((data[:cut], data[cut:])):
    path = os.path.join(src, f"part{n}")
    with open(path, "wb") as f:
        f.write(chunk)
    parts.append({"url": "file://" + path, "bytes": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
server.library_packs = lambda: [{"id": "lite", "label": "Essentials: test (0 GB)", "gb": 0.0, "parts": parts,
                                 "version": "2026-10-28", "install_bytes": 10_000}]
work = server.LIB + ".download"
os.makedirs(work, exist_ok=True)
with open(os.path.join(work, "full.000"), "wb") as f:  # left by an earlier choice of Everything
    f.write(b"x" * 1000)
server.start_job("library:lite", "Essentials", REAL_LIBRARY_WORKER, "lite")
check("pack installs from its parts", wait_for(lambda: server.downloads["library:lite"]["status"] not in server.ACTIVE)
      and server.downloads["library:lite"]["status"] == "done", server.downloads["library:lite"])
check("unpacked into the library folder", os.path.exists(os.path.join(server.LIB, "text", "a.md")))
with open(os.path.join(server.LIB, "pack.json")) as f:
    check("and knows which pack it is", json.load(f)["id"] == "lite")
check("the earlier choice's parts are gone", not os.path.exists(os.path.join(work, "full.000")))
check("and so is the download folder", not os.path.exists(work))

# ---------- moving the library (issue #9): same disk is a rename; another disk is a copy, then the old one goes ----------
server.MEMORY.set_setting("memory_ai_writes", False)  # a setting that must survive the folder settings
for case, same in (("same disk", True), ("another disk", False)):
    server.same_device = lambda a, b, same=same: same
    old_place = server.LIB
    dest = os.path.join(TMP, f"drive-{'same' if same else 'other'}")
    os.makedirs(dest)
    target = server.library_target(dest)
    server.start_job("library-move", "Moving the library", server.move_worker, target)
    check(f"move to {case}: finishes", wait_for(lambda: server.downloads["library-move"]["status"] not in server.ACTIVE)
          and server.downloads["library-move"]["status"] == "done", server.downloads["library-move"])
    check(f"move to {case}: the library is there", os.path.exists(os.path.join(target, "text", "a.md"))
          and server.LIB == target and server.search.LIB == target and server.DB_PATH == os.path.join(target, "index.sqlite"))
    check(f"move to {case}: the old copy is gone", not os.path.exists(old_place))
    with open(os.path.join(server.APP_DIR, "settings.json")) as f:
        settings = json.load(f)
    check(f"move to {case}: remembered, and other settings kept", settings.get("library_dir") == target
          and settings.get("memory_ai_writes") is False, settings)
check("a new start finds the moved library", server.search.chosen_folder("library_dir") == server.LIB)
check("a folder that already holds a library is used as it is", server.library_target(server.LIB) == server.LIB)
check("a missing folder is refused", server.folder_problem(os.path.join(TMP, "nope")))

# ---------- a folder with other things in it is never the library (review, Oct 28: switching deleted them) ----------
backup = os.path.join(TMP, "Backup")
os.makedirs(os.path.join(backup, "text"))
open(os.path.join(backup, "index.sqlite"), "wb").close()
open(os.path.join(backup, "photo.jpg"), "wb").close()
check("a library folder with photos in it: the library goes in a folder of its own inside it",
      server.library_target(backup) == os.path.join(backup, "Survival LLM Library"), server.library_target(backup))
os.remove(os.path.join(backup, "photo.jpg"))
check("the same folder with only the library in it: used as it is", server.library_target(backup) == backup)
open(os.path.join(backup, "photo.jpg"), "wb").close()
server.remove_library(backup)
check("removing a library leaves everything else", os.path.exists(os.path.join(backup, "photo.jpg"))
      and not os.path.exists(os.path.join(backup, "index.sqlite")) and not os.path.exists(os.path.join(backup, "text")))
saved_lib = server.LIB
server.LIB = backup
server.library_packs = lambda: [{"id": "lite", "label": "Essentials: test (0 GB)", "gb": 0.0, "parts": parts}]
try:
    REAL_LIBRARY_WORKER("library:lite", "lite")
    refused = ""
except RuntimeError as exc:
    refused = str(exc)
check("a library update won't replace a folder that holds other files", "other files" in refused
      and os.path.exists(os.path.join(backup, "photo.jpg")), refused)
server.LIB = saved_lib

# ---------- a move whose rename fails leaves the library working where it was ----------
version, where = server.lib_version[0], server.LIB
try:
    server.use_library_dir(os.path.join(TMP, "nowhere", "deeper", "Survival LLM Library"),
                           move_from=os.path.join(TMP, "does-not-exist"))
    failed = ""
except RuntimeError as exc:
    failed = str(exc)
check("a failed move: says so, keeps the library where it was, and threads reopen it",
      "Couldn't move" in failed and server.LIB == where and server.lib_version[0] > version, (failed, server.LIB))

# ---------- Your files in another folder ----------
other_files = os.path.join(TMP, "big-drive", "Documents")
os.makedirs(other_files)
with open(os.path.join(other_files, "plan.txt"), "w") as f:
    f.write("Our family meets at the library if the phones are down.")
server.use_files_dir(other_files)
check("Your files: the new folder is read", wait_for(lambda: any(i.get("name") == "plan.txt"
      for i in server.myfiles.items(server.MY_DB)), 15), server.myfiles.items(server.MY_DB))
with open(os.path.join(server.APP_DIR, "settings.json")) as f:
    check("Your files: remembered", json.load(f).get("files_dir") == other_files)

print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all setup checks passed'}")
sys.exit(1 if FAILS else 0)
