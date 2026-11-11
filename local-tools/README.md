# Local Windows commands

These helpers run the source checkout in browser mode and update it from the
author's repository. They also work when `origin` points to your own fork.

See [verification results and limits](VERIFICATION.md) for commands actually tested.

- `Setup.cmd`: creates `.venv` and installs two browser-mode Python dependencies.
  Requires Python 3.12+. Pass `-PythonPath C:\path\to\python.exe` if needed.
- `Start.cmd`: prepares a missing `.venv` and browser-mode dependencies on first
  start, then opens the original app in your browser. Python 3.12+ is required;
  the first preparation needs internet. Subsequent starts reuse the environment.
  An incomplete environment is preserved and reported, never deleted automatically.
  Stop with Ctrl+C in its terminal.
- `Update.cmd`: fetches the author's `main` directly from
  `https://github.com/anonnerdfrenzy/survival-llm.git`, independently of `origin`.
  It works on a local feature branch or `main` and applies only fast-forward
  updates. Local commits are preserved. If both sides have new commits, it stops
  with the fetched commit ID for a manual review and merge. It refuses detached
  HEAD, unfinished Git operations, modified tracked files and a running instance.
  Git also refuses to overwrite conflicting untracked files.

Add `-CheckOnly` to any command for a read-only preflight. No setup, server,
model/library download or Git fetch is performed in this mode.
Exit code 0 means the diagnostic report was produced, not that everything is
ready. Read `environmentReady` and `issues`: they check Python 3.12+, a real
virtual environment and dependency imports. `ollamaInstalled` only reports the
executable; it does not confirm a running engine, an installed model or a library.

Launcher regression checks after setup:
`.venv\Scripts\python.exe local-tools/test_windows_start.py`. They exercise the
actual CMD entry points from outside a project folder with spaces: first and
repeated starts, setup, dependency repair, preflight and failure exit codes.
Local fixture packages keep the tests offline.

The app uses [Ollama](https://ollama.com/) installed on the computer. Open Ollama
before use if needed; the original app can also detect/start an installed engine.
Models and the offline library are chosen in the original setup interface. They
can be large; these command files do not download them or change Ollama settings.
The source launcher uses upstream's existing development-mode flag to disable the
packaged app's self-updater; source updates go through `Update.cmd` instead.

Survival LLM is an offline assistant and reference library, not a gateway for free
cloud providers. The separate `FreeLLMAPI` project in this workspace provides the
multi-provider gateway described in its own README.

No push, commit, deployment, auto-start task or remote repository write is performed
by these commands. Upstream README and license remain in the repository root.

## Working with a fork

Create a fork of `anonnerdfrenzy/survival-llm` on GitHub in your own account.
Keep this existing checkout: it already contains the local work. After creating
the fork, configure its remotes manually (replace YOUR_ACCOUNT):

```powershell
git remote rename origin upstream
git remote add origin https://github.com/YOUR_ACCOUNT/survival-llm.git
git remote -v
```

These commands assume the original layout: `origin` points to the author and no
`upstream` remote exists. Inspect `git remote -v` first; do not repeat the rename
if the remotes are already configured. `Update.cmd` works with either layout.

Keep `main` aligned with the author's history and develop on feature branches.
Publish your commits and open pull requests manually. This command does not
synchronize your GitHub fork: fetching/updating locally and publishing are
separate actions.

When histories diverge, preserve your uncommitted work first and review the
upstream changes. To integrate on your feature branch without an automatic
merge commit:

```powershell
git fetch --no-tags upstream main
git diff HEAD...FETCH_HEAD
git merge --no-commit --no-ff FETCH_HEAD
```

Resolve conflicts, run the tests, then commit manually when satisfied. To cancel
an in-progress merge, use `git merge --abort`. Do not reset your feature branch
to upstream: that would remove its local commits from the branch.

The updater can be tested without internet, Ollama, model downloads or new
commits: `.venv\Scripts\python.exe local-tools/test_source_update.py`
(Windows with Git/PowerShell, after setup).

## Formatting and development checks

Node.js/npm are optional developer tools; running the Python application does
not require them. To use the pinned Prettier version:

```powershell
npm ci
npm run format
npm run format:check
```

The commands cover the browser UI, extracted website assets and tooling
configuration. They do not format Python, PowerShell or downloaded libraries.
`docs/.prettierrc` is the shared configuration; the root configuration forwards
to it. Shell/Makefile formatting is not enabled because no shell parser plugin
is installed.

When opening this repository as a VS Code folder, install the recommended
Prettier extension to format HTML, CSS, JavaScript and JSON on save. The local
dependency and lockfile keep command-line and editor formatting consistent.

Run `.venv\Scripts\python.exe tests/run_all.py` for the application tests, including HTTP checks
of the relocated static assets and a test of the packaging copy function. Bash
is needed for the packaging check (Git Bash on Windows); it does not download
build dependencies or package a release. Run `.venv\Scripts\python.exe local-tools/test_source_update.py`
separately on Windows for the source updater.

The Windows folder icon uses `docs/src/assets/folder.ico`, referenced by the
root `desktop.ini`. Windows also requires the directory's ReadOnly customization
attribute and the file's Hidden/System attributes; Git does not preserve these.
To apply them locally, run `attrib +r .` and `attrib +h +s desktop.ini` from the
repository root. This changes folder appearance, not write access to its files.
