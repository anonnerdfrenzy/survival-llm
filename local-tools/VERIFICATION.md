# Windows source command verification

Verified on 2026-11-12 on this Windows workstation using Python 3.12.14.
This records execution evidence for the source checkout, not installer or macOS
certification. No remote repository writes were performed.

| Command or scenario | Observed result |
| --- | --- |
| `Setup.cmd` | Exit 0. Real `.venv`, pypdf 6.19.0 and truststore 0.10.4 installed; repeat with `PIP_NO_INDEX=1` also passed. |
| `Start.cmd` | Real server started at `http://127.0.0.1:8765/`. Repeated invocation returned 0 and found the existing instance. |
| `Start.cmd -CheckOnly` | Exit 0; `environmentReady: true`, Python 3.12.14, empty `issues`. This is a diagnostic report, not a model inference test. |
| `Setup.cmd -CheckOnly` | Exit 0 on the workstation; reported Python 3.12.14, ready environment and empty issues without running setup. |
| `Update.cmd -CheckOnly` | Passed the regression checks; no fetch and no change to FETCH_HEAD. |
| `Update.cmd` while app runs | Exit 1, `Close this Survival LLM instance before updating.` Working source was not updated. |
| `.venv\Scripts\python.exe local-tools/test_windows_start.py -v` | 7 tests passed. Actual CMD files run from another directory with spaces in the project path. First/repeated launch, repeated setup, missing dependency repair, broken import diagnosis, incomplete environment preservation, server failure exit and update preflight are covered. |
| `.venv\Scripts\python.exe local-tools/test_source_update.py` | 9 tests passed on temporary local repositories: fast-forward, local history preservation, dirty files, conflicting untracked file, detached HEAD, pending merge, fetch failure, divergence decision and read-only preflight. |
| `.venv\Scripts\python.exe tests/run_all.py` | All 13 test files passed, including HTTP static assets and the packaging asset-copy function. |
| `npm ci` | Exit 0, installed the locked development dependency; npm audit reported 0 vulnerabilities. |
| `npm run format` | Exit 0; checked files were already formatted. |
| `npm run format:check` | Exit 0. |
| `git diff --check` | Exit 0. |

The updater tests initially failed because the agent sandbox blocked Git Bash
with `NtCreateDirectoryObject ... 0xC0000022`. Running the same suite outside that
sandbox passed. That failure was not an application update failure.

## Runtime evidence

- Real running instance: `/`, `/static/src/js/app.js`, `/static/src/css/app.css`
  and authenticated `/api/status` returned HTTP 200.
- Status reported Ollama running and four installed models. The offline library
  was absent (`library: null`); no library was downloaded during verification.
- An isolated instance of the actual server, with temporary settings/files/library
  directories, called the already installed `qwen3:4b` through `/api/chat`.
  The response contained `done`, `answer: "OK"`, `cut_off: false` and
  `unfinished: false`; no error event or transport error occurred. The temporary
  server was stopped after the check. No model download was needed.

## Fixed gaps and remaining limits

Previously Start required Setup to have already run. It now prepares a missing
environment and installs missing browser dependencies. An incomplete existing
environment is retained with an actionable error instead of being deleted.

Previously preflight called an environment ready solely because its Python file
existed. A regression test reproduced a false positive with an import that raised
an exception. The probe now runs Python in isolated mode without writing bytecode,
checks version and virtual-environment identity, and imports both dependencies.
Setup verifies this too before reporting success; Start rejects an invalid runtime.

Readiness covers the Python runtime and importability, not dependency version
equality or the correctness of every application feature. Setup applies pinned
requirements. Preflight exit 0 means JSON was produced: inspect `environmentReady`
and `issues`. Ollama installation, engine availability and successful inference
are distinct checks.

Not verified here: visual browser interaction, offline-library download/search,
all four models, upstream network fetching into the working branch, complete
release builds/installers, macOS/Linux commands, VS Code extension behavior and
Explorer icon rendering. Remote/fork configuration instructions are manual
operations and were not executed. The packaging test checks asset copying only.
