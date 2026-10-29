"""Checks for issue #17 (app/server.py): a Windows PC without WebView2 got a broken window (pywebview quietly used
Internet Explorer's engine). The app now checks for WebView2 the way pywebview does, runs Microsoft's installer when
it's missing, and only if that fails says so and opens in the browser. A PC that has it must never see the installer.
No Windows needed: the registry, the installer, pywebview's engine choice and the message box are stand-ins.

Usage: .venv/bin/python tests/webview2_test.py"""
import os
import sys
import tempfile
import types

TMP = tempfile.mkdtemp(prefix="webview2-test-")
os.environ.update(SURVIVAL_LLM_APP_DIR=os.path.join(TMP, "settings"), SURVIVAL_LLM_FILES=os.path.join(TMP, "files"),
                  SURVIVAL_LLM_LIBRARY=os.path.join(TMP, "library"), OLLAMA_HOST="127.0.0.1:9")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import server  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


# ---- a stand-in Windows registry ----
NET = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
RUNTIME = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
MACHINE = rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{RUNTIME}"
USER = rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{RUNTIME}"
registry = {}


class Key:
    def __init__(self, values):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def open_key(hive, path):
    if (hive, path) not in registry:
        raise FileNotFoundError(path)
    return Key(registry[(hive, path)])


def query(key, name):
    if name not in key.values:
        raise FileNotFoundError(name)
    return key.values[name], 1


sys.modules["winreg"] = types.SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", HKEY_CURRENT_USER="HKCU",
                                              OpenKey=open_key, QueryValueEx=query)
server.platform.machine = lambda: "AMD64"


def pc(net=528372, machine_pv=None, user_pv=None):
    registry.clear()
    if net is not None:
        registry[("HKLM", NET)] = {"Release": net}
    if machine_pv is not None:
        registry[("HKLM", MACHINE)] = {"pv": machine_pv}
    if user_pv is not None:
        registry[("HKCU", USER)] = {"pv": user_pv}


for name, setup, want in [
        ("WebView2 for the whole PC (the usual case)", dict(machine_pv="130.0.2849.80"), True),
        ("WebView2 for this user only", dict(user_pv="128.0.2739.42"), True),
        ("no WebView2 at all (issue #17)", dict(), False),
        ("WebView2 removed: the key is left with version 0.0.0.0", dict(machine_pv="0.0.0.0"), False),
        ("a WebView2 older than 86", dict(machine_pv="85.0.564.0"), False),
        ("an empty version", dict(machine_pv=""), False),
        ("WebView2 but .NET older than 4.6.2", dict(net=394000, machine_pv="130.0.2849.80"), False),
        ("no .NET 4 key", dict(net=None, machine_pv="130.0.2849.80"), False)]:
    pc(**setup)
    check(f"webview2_ready: {name}", server.webview2_ready() is want, server.webview2_ready())

# ---- what happens at launch ----
ran, boxes = [], []
engine = {"chromium": False}
server.subprocess.run = lambda cmd, **kw: ran.append(cmd)
server.ctypes.windll = types.SimpleNamespace(user32=types.SimpleNamespace(MessageBoxW=lambda *a: boxes.append(a[1])))
platforms = types.ModuleType("webview.platforms")
sys.modules["webview.platforms"] = platforms
sys.modules["webview.platforms.winforms"] = platforms.winforms = types.SimpleNamespace()
setup_exe = os.path.join(TMP, "MicrosoftEdgeWebview2Setup.exe")
open(setup_exe, "wb").write(b"MZ")
server.WEBVIEW2_SETUP = setup_exe


def launch(installed_after):
    ran.clear(), boxes.clear()
    platforms.winforms.is_chromium = installed_after
    return server.ensure_webview2()


pc(machine_pv="130.0.2849.80")
ok = launch(installed_after=True)
check("a PC with WebView2 opens the window without running the installer", ok and not ran and not boxes, (ok, ran, boxes))

pc()
ok = launch(installed_after=True)
check("a PC without WebView2 runs Microsoft's installer, then opens the window",
      ok and ran == [[setup_exe, "/install"]] and not boxes, (ok, ran, boxes))

ok = launch(installed_after=False)
check("when the install fails it says so once and opens in the browser",
      ok is False and len(ran) == 1 and len(boxes) == 1 and server.WEBVIEW2_URL in boxes[0], (ok, ran, boxes))

server.WEBVIEW2_SETUP = os.path.join(TMP, "missing.exe")
ok = launch(installed_after=True)
check("with no installer next to the app (run from source) it says so and opens in the browser",
      ok is False and not ran and len(boxes) == 1, (ok, ran, boxes))
server.WEBVIEW2_SETUP = setup_exe


def broken(*a, **kw):
    raise RuntimeError("registry unreadable")


real = server.webview2_ready
server.webview2_ready = broken
ok = launch(installed_after=False)
check("a check that fails doesn't stop the app: it opens the window as before", ok and not ran and not boxes,
      (ok, ran, boxes))
server.webview2_ready = real

print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all passed'}")
sys.exit(1 if FAILS else 0)
