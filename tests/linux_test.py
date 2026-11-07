"""Linux support: where the AI engine goes and how it unpacks, the Trash, and the Agorisme wiki's conversion.

Usage: python3 tests/linux_test.py
Runs on any system (the Linux-only parts are called directly); nothing is downloaded.
"""
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

TMP = tempfile.mkdtemp(prefix="linux-test-")
os.environ.update(SURVIVAL_LLM_APP_DIR=os.path.join(TMP, "settings"), SURVIVAL_LLM_FILES=os.path.join(TMP, "files"),
                  SURVIVAL_LLM_LIBRARY=os.path.join(TMP, "library"), OLLAMA_HOST="127.0.0.1:9",
                  XDG_DATA_HOME=os.path.join(TMP, "data"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, ROOT)
import server  # noqa: E402
from library import fetch_agorismewiki as wiki  # noqa: E402

failures = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


if sys.platform.startswith("linux"):
    check("engine goes in XDG_DATA_HOME", server.ENGINE == os.path.join(TMP, "data", "survival-llm", "ollama", "bin",
                                                                         "ollama"))
    check("engine download unpacks into the folder above bin/", server.ENGINE_DIR == os.path.join(
        TMP, "data", "survival-llm", "ollama"))
    info = server.engine_info()
    check("Linux offers its engine download", bool(info) and info["url"].endswith(".tar.zst") and len(info["sha256"]) == 64)
check("both Linux machines are pinned to one version",
      len({e["version"] for e in server.LINUX_ENGINES.values()}) == 1)
check("Linux pick models from the GGUF builds", server.system_key() == ("mac" if sys.platform == "darwin" else "win"))

# A small .tar.zst laid out like Ollama's (bin/ollama, lib/ollama/...), if this computer can make one.
src = os.path.join(TMP, "src")
os.makedirs(os.path.join(src, "bin"))
os.makedirs(os.path.join(src, "lib", "ollama"))
with open(os.path.join(src, "bin", "ollama"), "w") as f:
    f.write("#!/bin/sh\necho ollama version is 0.40.11\n")
open(os.path.join(src, "lib", "ollama", "libggml.so"), "w").close()
archive = os.path.join(TMP, "ollama.tar.zst")
made = shutil.which("zstd") and subprocess.run(["tar", "--zstd", "-cf", archive, "-C", src, "bin", "lib"]).returncode == 0
if made:
    dest = os.path.join(TMP, "unpacked")
    server.unpack_tar_zst(archive, dest)
    check("tar.zst unpacks with bin/ and lib/", os.path.isfile(os.path.join(dest, "bin", "ollama"))
          and os.path.isfile(os.path.join(dest, "lib", "ollama", "libggml.so")))
else:
    print("SKIP tar.zst unpacking (no zstd here)")
try:
    server.unpack_tar_zst(os.path.join(TMP, "missing.tar.zst"), os.path.join(TMP, "never"))
    check("a broken engine download says what went wrong", False)
except RuntimeError as exc:
    check("a broken engine download says what went wrong", "zstd" in str(exc)
          and not os.path.exists(os.path.join(TMP, "never")))

# The freedesktop.org Trash (gio hidden, so nothing goes in this computer's real Trash).
path = os.environ["PATH"]
os.environ["PATH"] = ""
try:
    for n in range(2):
        doomed = os.path.join(TMP, "plan.txt")
        with open(doomed, "w") as f:
            f.write(f"copy {n}")
        server.linux_trash(doomed)
finally:
    os.environ["PATH"] = path
trash = os.path.join(TMP, "data", "Trash")
check("removed file is in the Trash, not deleted", not os.path.exists(os.path.join(TMP, "plan.txt"))
      and sorted(os.listdir(os.path.join(trash, "files"))) == ["plan.2.txt", "plan.txt"])
with open(os.path.join(trash, "info", "plan.txt.trashinfo")) as f:
    info = f.read()
check("Trash remembers where it came from", info.startswith("[Trash Info]\nPath=/") and "DeletionDate=" in info)

# The Agorisme wiki's Zola Markdown.
title, body = wiki.front_matter('---\ntitle: Voedsel bewaren\ntaxonomies:\n  categorie:\n    - X\n---\n\nTekst')
check("wiki front matter gives the title", title == "Voedsel bewaren" and body.strip() == "Tekst")
text = wiki.plain('{% warning(title="Let op") %}\nKook water.\n{% end %}\nZie [water](@/zelfvoorzienend-in-water.md)'
                  ' en ![Hark](/images/hark.png) of [home](/agorisme/).')
check("wiki shortcodes, links and images become plain Markdown",
      text == "**Let op: Let op**\nKook water.\n\nZie [water](https://agorismewiki.nl/zelfvoorzienend-in-water/) en "
              "(afbeelding: Hark) of [home](https://agorismewiki.nl/agorisme/).")
check("wiki home page address", wiki.page_url("_index.md") == "https://agorismewiki.nl/")

# ---- the graphics card in the ranking ----
real_ram = server.ram_gb
server.ram_gb = lambda: 64
server.disk_free_gb = lambda path=None: 500


def ranking(gpu):
    server._gpu[:] = [gpu]
    rows = server.machine_catalog([])
    return {r["key"]: r for r in rows}, next((r["key"] for r in rows if r["recommended"]), None)


if sys.platform != "darwin":
    rows, best = ranking(None)
    check("no card found: ranked as before", best == "nemotron-lightning" and not any(r["slow_here"] for r in rows.values()))
    rows, best = ranking({"vendor": "amd", "name": "", "vram_gb": 16, "usable": True})
    check("16 GB card: Qwen 27B (18 GB, dense) is slow, mixture of experts isn't",
          rows["qwen-27b"]["slow_here"] and not rows["nemotron-lightning"]["slow_here"]
          and not rows["granite-8b"]["slow_here"] and best == "nemotron-lightning")
    rows, best = ranking({"vendor": "nvidia", "name": "RTX 4090", "vram_gb": 24, "usable": True})
    check("24 GB card: Qwen 27B is quick", not rows["qwen-27b"]["slow_here"])
    server.ram_gb = lambda: 16
    rows, best = ranking({"vendor": "nvidia", "name": "RTX 4060", "vram_gb": 8, "usable": True})
    check("16 GB RAM, 8 GB card: Granite (fits the card) over Gemma (doesn't)",
          best == "granite-8b" and rows["gemma-e4b"]["slow_here"])
    rows, best = ranking({"vendor": "amd", "name": "", "vram_gb": 16, "usable": False})
    check("a card the engine can't use: dense models are slow, the pick still falls back to one that fits",
          rows["granite-8b"]["slow_here"] and best == "granite-8b")
    server.ram_gb = lambda: 16
    rows, best = ranking({"vendor": "nvidia", "name": "", "vram_gb": 16, "usable": True})
    check("untested models are offered but never recommended",
          rows["gpt-oss-20b"]["untested"] and rows["gpt-oss-20b"]["fits"] and best == "granite-8b")
server.ram_gb = real_ram

# ---- AMD on Linux: the engine comes with ROCm, unpacked over it ----
if sys.platform.startswith("linux") and made:
    server._gpu[:] = [{"vendor": "amd", "name": "", "vram_gb": 16, "usable": True}]
    info = server.engine_info()
    check("AMD card: the engine download adds ROCm", [a["url"] for a in info.get("addons", [])]
          == [server.LINUX_ENGINES["x86_64"]["rocm"]["url"]] if "x86_64" in os.uname().machine else True)
    rocm_src = os.path.join(TMP, "rocm")
    os.makedirs(os.path.join(rocm_src, "lib", "ollama", "rocm_v7_2"))
    open(os.path.join(rocm_src, "lib", "ollama", "rocm_v7_2", "libamdhip64.so.7"), "w").close()
    rocm = os.path.join(TMP, "rocm.tar.zst")
    subprocess.run(["tar", "--zstd", "-cf", rocm, "-C", rocm_src, "lib"], check=True)
    files = {"https://example/main.tar.zst": archive, "https://example/rocm.tar.zst": rocm}
    fake = {"url": "https://example/main.tar.zst", "bytes": os.path.getsize(archive), "sha256": server._sha256(archive), "version": "x",
            "addons": [{"url": "https://example/rocm.tar.zst", "bytes": os.path.getsize(rocm), "sha256": server._sha256(rocm)}]}
    server.engine_info = lambda: fake
    server._download = lambda key, url, path, size, done_before=0, total=None: shutil.copy(files[url], path)
    server._update = lambda *a, **k: None
    server.start_ollama = lambda: None
    server.engine_worker("engine")
    d = server.ENGINE_DIR
    check("engine and ROCm unpacked into one folder", os.path.isfile(os.path.join(d, "bin", "ollama"))
          and os.path.isfile(os.path.join(d, "lib", "ollama", "libggml.so"))
          and os.path.isfile(os.path.join(d, "lib", "ollama", "rocm_v7_2", "libamdhip64.so.7")))
    check("downloads cleaned up", not [f for f in os.listdir(os.path.dirname(d)) if f.endswith(".tar.zst")])

shutil.rmtree(TMP, ignore_errors=True)
print(f"{len(failures)} failed" if failures else "all Linux checks passed")
sys.exit(1 if failures else 0)
