# Survival LLM

A free AI assistant and survival library that runs entirely on your own computer and works with no
internet. Ask it how to keep food safe in a blackout, treat a burn or purify water: it searches an
offline library of medical, emergency, how-to and encyclopedia articles, answers from what it finds,
and shows you the exact passage each answer came from.

- **Offline and private.** The AI model and the library live on your computer. Your questions never leave it, and once set up it works with the internet off.
- **Shows its sources.** Every answer lists the articles it read; click one to read it yourself, cited passage highlighted, with its license. Ask "where did you get that?" and it opens the source.
- **Shows its reasoning.** Show reasoning, under each answer, opens what the AI thought before it answered, step by step, with the searches and articles it read in between. It stays hidden until you click it. How much it reasons is up to you: Reasoning, next to Send, is a budget (Off, 1,000, 4,000 or 16,000 tokens, or no limit), and at the limit its thinking stops and it answers from what it has.
- **Yours to adjust.** The Instructions button shows the instructions the AI gets before you ask anything (the app adds today's date, the names of your files and your Memory notes after them); edit them and Save to change how it answers (Reset brings back the original). The Length limit next to Send sets how long an answer may run, or turns the limit off.
- **Add your own files.** Your files, at the top, takes PDFs, Word documents, EPUB ebooks, web pages and text files (drop them on the window or choose them), so the AI can search your generator's manual, your medicines list or your family's emergency plan along with the library. They stay on your computer, in the `Survival LLM Files` folder in your home folder; files you put in that folder, or change there, are picked up on their own. It can't read scans or photos of pages yet.
- **Remembers you.** Tell it your daughter is allergic to penicillin or that you have a Honda generator, and it saves a short note so later chats know it too; each answer shows what it saved, with Undo. Memory, at the top, shows every note in one list you can edit, and a switch turns off the AI's saving (it still reads the notes you keep). The notes stay on your computer, in one plain text file with the app's settings.
- **Your library, your way.** Library, at the top, shows every source in your library, downloads it again (to repair it or start over), switches between Essentials and Everything, moves it to another folder or drive, and adds extra sources from their own websites, such as the Dutch Agorisme wiki. To offer another extra source, add it to `library/addons.py`.
- **Updates itself.** Check for updates, at the bottom of the window, looks for a new version (it also looks once a day while it runs, by fetching one small file from the project's web page; nothing about you is sent). Update now downloads it, checks it, and restarts into it, keeping your models, library, files and settings. Newer libraries are offered there too.
- **Built for emergencies.** About 1.5 million articles (500,000 in the smaller download): about 930,000 of Wikipedia's most-read articles, WikiMed, MedlinePlus, a UK medicines guide, WikEM, Ready.gov, CDC, U.S. military and FEMA survival and first-aid manuals, the USDA canning guide, risk references for estimating micromorts (life tables, U.S. death rates), wikiHow, iFixit, Appropedia, Energypedia and practical Q&A. See [SOURCES.md](SOURCES.md).

## Install

Do this while you have internet. After that, it needs none. Setup takes 20 minutes to about 2½ hours, depending on
your computer and internet speed (the biggest AI model is 80 GB); you only click for about 5 minutes.

**Mac** (Apple Silicon, macOS 14 Sonoma or newer)
1. Download `Survival-LLM-mac.zip` and double-click it to unzip. Move **Survival LLM** to Applications if you like.
2. Double-click **Survival LLM**. The first time, macOS says it can't verify the app, because it isn't sold through
   Apple. Click **Done**, open **System Settings > Privacy & Security**, scroll down to "Survival LLM was blocked",
   click **Open Anyway**, and confirm with your password. You only do this once.

**Windows** (10 or 11, 64-bit)
1. Download `Survival-LLM-windows.zip`, right-click it and choose **Extract All**. (Running it from inside the zip doesn't work.)
2. Open the extracted **Survival LLM** folder and double-click **Survival LLM.bat**. If Windows says it protected
   your PC, click **More info**, then **Run anyway**.

**Linux** (64-bit Intel/AMD or ARM; runs from this repository)
1. Install Python 3.11 or newer, git and zstd, plus GTK WebKit for the app window (without it the app opens in your
   web browser): `sudo apt install git zstd python3-venv python3-gi gir1.2-webkit2-4.1` on Debian, Ubuntu or Mint;
   `sudo dnf install git zstd python3-gobject webkit2gtk4.1` on Fedora.
2. `git clone https://github.com/milovanderlinden/survival-llm.git && cd survival-llm && bin/install-linux`
3. Open **Survival LLM** from your app menu, or run `survival-llm`. To update later: `git pull` in that folder.

**Then** the app opens in its own window and walks you through setup:
1. **AI engine:** built into the Mac app. On Windows and Linux, one click downloads it (Ollama, 1.6 GB on Windows,
   1.5 GB on Linux; it runs on NVIDIA graphics cards or the processor). An Ollama you have installed already is used
   instead; for AMD graphics cards, install Ollama from ollama.com.
2. **AI model:** it suggests the best one for your computer's memory (below) and downloads it.
3. **Library:** "Everything" (8.8 GB download) or "Essentials" (1.3 GB, without Wikipedia and iFixit).

**Free disk space needed:** the model's size plus 5 GB, plus about 27 GB while the full library installs
(21 GB once installed), or about 10 GB for Essentials (3 GB once installed).

## Uninstall

On Linux, run `bin/install-linux --uninstall` and delete the repository folder, then the folders below (the AI
engine is in `~/.local/share/survival-llm`, the settings in `~/.survival-llm`). Elsewhere, delete the app, then these folders: the AI models, in `~/.ollama/models` (shared with any other Ollama on the
computer, so keep it if you use Ollama elsewhere), and the library. The app's Library window (Search library, then
Switch or move the library) shows where the library is: in `~/Survival LLM Library` if you installed it before 0.4, otherwise
in the app's settings folder unless you moved it. Your own files are in `~/Survival LLM Files` unless you picked
another folder; keep it if you want them. The app's own settings are in `~/Library/Application Support/Survival LLM`
on a Mac, and in `%APPDATA%\Survival LLM` plus the AI engine and library in `%LOCALAPPDATA%\Survival LLM` on Windows.

## In Dutch (Nederlands)

Choose **Nederlands** under Language, at the bottom of the window (it starts in Dutch on a computer set to Dutch).
The whole window switches to Dutch, and the AI answers in Dutch: it still searches the mostly English library (with
English keywords), translates what it reads, uses 112 as the emergency number, and ends with a "Bronnen:" line that
the app checks like a "Sources:" line. Its instructions stay in English, as tested, with a Dutch section added after
them; its notes in Memory stay in English too, because the app's checks on them read English. The terminal version
takes `--dutch`.

For Dutch articles in the library, add the [Agorisme wiki](https://agorismewiki.nl) (self-sufficiency, food storage,
water, energy, local economy; about 40 articles): click **Library** at the top, then **Add Agorisme wiki** under
Extra sources. Update and Remove are there too, and it comes back by itself after a library update. The wiki states
no license, so it is never in the library downloads (see SOURCES.md). From the terminal, with the app closed:
`python3 library/fetch_agorismewiki.py --install`.

The model tests below were all in English; how well each model answers in Dutch hasn't been measured.

### Adding a language

The app writes English; `app/static/i18n.js` translates the window as it appears, from a language pack. To add one:

1. Copy `app/static/lang-nl.js` to `app/static/lang-<code>.js` (an ISO 639-1 code, like `de`), change the code in its
   `register` line, and translate its values. The keys are the English the app writes; strings with numbers or names
   in them are patterns. Anything it leaves out shows in English.
2. In `core.py`, add the language to `LANGUAGES` (its name in the Language menu, in that language, and in English),
   `LANGUAGE_PROMPTS` (what to tell the AI: answer in that language, search the English library in English, the
   country's emergency number, the word for "Sources") and `SOURCES_WORDS`.

That's all: the menu, loading the pack and starting in the computer's own language follow from those. Run
`python3 tests/run_all.py`; `tests/languages_test.py` checks that each language has all its parts. The memory
step's triggers (`PERSONAL` in `core.py`) and search's filler words (`STOPWORDS` in `library/search.py`) know English
and Dutch; add the new language's common words there too, or memory saving and searches work less well in it.

## Which model your computer gets

The app checks your memory and suggests a model. More memory, smarter model.

| Your computer | Model | Download |
|---|---|---|
| Mac with 128 GB or more | NVIDIA Nemotron 3.5 Super (`nemotron-3.5-super:120b-a12b-nvfp4`) | 80 GB |
| Mac with 32-96 GB | Qwen3.8 27B (`qwen3.8:27b-mlx`) | 18 GB |
| Windows or Linux PC with 32 GB or more | NVIDIA Nemotron 3.5 Lightning (`nemotron-3.5-lightning:30b-a3b`) | 25 GB |
| Mac or PC with 16-31 GB | IBM Granite 4.2 8B (`granite4.2:8b`) | 6 GB |

Nemotron Super needs 128 GB because macOS lets the graphics side use only about three quarters of memory.

On a Windows or Linux PC the app also looks at the graphics card (the setup screen and the Model window name it). A
model that isn't a mixture of experts is only quick when it fits in the card's memory with about 2 GB to spare, so
one that doesn't is marked "slow here" and the next one is recommended; the Nemotron models stay quick either way, as
only about 3 billion of their parameters work on each word. On Linux with an AMD card, the app's AI engine comes with
Ollama's ROCm libraries (1 GB more) so it uses the card. On Windows the app's own engine can't use AMD cards; the
Ollama app from ollama.com can.

Also offered, marked "Not tested yet" and never recommended until they are: OpenAI's gpt-oss 20B (`gpt-oss:20b`,
14 GB) and Qwen3 30B-A3B (`qwen3:30b-a3b`, 19 GB), two mixtures of experts in Lightning's size class. Qwen models are
also a candidate for the Dutch interface.

Gemma 4 E4B (`gemma4`, 10 GB) is offered as a faster option for 16 GB computers. Computers with 8 GB can
still search the library; no model we tested was both small enough and safe enough to recommend for them.

## How the models did

Each model answered 22 blackout and first-aid questions (food, generators, water, carbon monoxide,
hypothermia, bleeding, burns, insulin, downed lines, fallout, botulism and more) using the full app: its
prompt, tools and library search. Independent AI judges then graded every answer blind (model names hidden,
order shuffled) against official guidance from USDA, CDC, FEMA, EPA, NHS, WHO and the Red Cross: one judge
for accuracy, one for safety, and a skeptic who re-checked every answer flagged as harmful.

How these numbers were measured, plainly: the tests ran on an earlier build of the library, before Wikipedia
was added, which also held some material that isn't in the public downloads (the Kiwix "zimgit" collections and
MedlinePlus's licensed encyclopedia and drug pages; 1 to 10 answers per model read one of those). The app's
instructions have also gained rules since: the carbon monoxide rule and "always give your best estimate". Treat
the table as a comparison between models, not a guarantee for the version you download.

| Model | Accuracy | Main point right | Harmful answers | Seconds per answer* |
|---|---|---|---|---|
| Nemotron 3.5 Super | 86% | 21 of 22 | 0 | 12 |
| Qwen3.8 27B | 80% | 21 of 22 | 0 | 40 |
| Nemotron 3.5 Lightning | 77% | 19 of 22 | 1 | 8 |
| Qwen 3.6 (36B MoE) | 59% | 15 of 22 | 1 | 24 |
| Granite 4.2 8B | 55% | 14 of 22 | 0 | 29 |
| Granite 4.2 30B | 55% | 11 of 22 | 2 | 55 |
| Gemma 4 E4B | 48% | 11 of 22 | 0 | 3 |
| Granite 4.2 3B | 44% | 8 of 22 | 5 (2 could kill) | 12 |

\* On an M4 Max MacBook Pro (128 GB), Ollama 0.40.9. Qwen3.8 27B was tested as mlx-community's 4-bit build
(`local-ai2` in `evals/results`); the app downloads Ollama's NVFP4 build of the same model. Nemotron Super appears
there as `local-ai1` (the same model with the app's settings). Windows downloads a different file of Nemotron
Lightning (Q4_K_M) than the Mac build tested here. Accuracy is the share of points on a 0-3 scale per answer; "harmful"
means following it could hurt someone. Granite 4.2 3B, first planned for 8 GB computers, is not offered: it
told people not to use a tourniquet on an arm and to stay 3 feet from a downed power line (the guidance is 35).
Qwen 3.6 is not offered either: it got stuck repeating itself on two questions (once for 94 minutes),
which is also why answers have a length limit (you can change it, or turn it off, next to Send).

The tests found and fixed two problems for every model: some kept looking things up until they ran out of
lookups and never answered (now they are told to answer from what they read), and several gave "if you
must" exceptions for running cars and generators near the house (the prompt now rules those out).
Reproduce with `evals/retrieval_eval.py`, `evals/make_judging_batches.py` and `evals/score_judging.py`;
answers are in `evals/results/`, grades in `evals/judging/`.

**Made-up sources.** Each answer ends with the model's own "Sources:" line, and its instructions say the app shows
every article it opened. Models name sources they never saw anyway. In a separate test of 14 questions
(`evals/citation_check.py`, October 24 2026), these answers named a source the model had neither opened nor seen in
its search results: Nemotron Super 6 (mostly answering from memory and naming Ready.gov or the CDC), Lightning 3,
Gemma 3, Granite 2 and Qwen3.8 27B 1. So the app checks that line against what the model opened or saw, and replaces
a line that names anything else with the list of articles it actually read.

## How it works

```
your question ─► local model (Ollama) ─► search_library ─► SQLite full-text index ─► passages
                        ▲                read_article  ─► plain-text library files
                        └──── answer with "Sources:" ◄──┘   show_article ─► opens it on screen
```

- `app/server.py` serves the chat page on `127.0.0.1` only and runs each turn through `core.py`.
- `core.py` streams the model's answer and runs its library tools: `search_library`, `read_article`, `show_article`.
- `library/search.py` searches `index.sqlite` (FTS5, BM25 ranking over ~1,500-character passages, official sources ranked higher) and reads the plain-text Markdown shards.
- `memory.py` keeps the AI's notes about the person (`survival-llm-memory.txt`, with the app's settings) and, while the person allows it, `core.py` gives the model one short extra turn after answers to messages about the person or their family, to say what to remember, change or forget (a JSON reply the app checks and applies). The notes, today's date and the names of the person's files are added after the instructions when a chat starts.
- `library/myfiles.py` reads the person's own files into a small index of their own (kept with the app's settings) and searches it together with the library.
- Everything except Ollama, the app window (pywebview), PDF reading (pypdf) and checking web certificates with the system's own store (truststore) is the Python standard library.

## Run from source

```bash
python3 app/server.py          # the app in its own window (needs `pip install pywebview pypdf truststore`; else it uses your browser)
                               # on Linux, bin/install-linux sets this up in .venv-app
python3 app/server.py --browser                     # in your web browser instead
python3 chat.py "How long is fridge food safe in a blackout?"   # terminal; --model NAME picks a model
```

The library is looked up at `$SURVIVAL_LLM_LIBRARY`, then the folder picked in the app (`library_dir` in its
`settings.json`), then `~/Survival LLM Library`, then `library.noindex/` next to the code; a new one goes in the app's
settings folder (`Library.noindex` on a Mac, `%LOCALAPPDATA%\Survival LLM\Library` on Windows).
Without a built-in engine, the app uses an Ollama you have installed (`ollama serve`).

`python3 tests/run_all.py` checks memory and the handling of what models write (forget requests, notes about different
people, Sources lines), with a stand-in for the model: no Ollama or library needed. Run it after changing `memory.py` or
`core.py`, and `evals/memory_eval.py --step MODEL ...` to see how real models do.

## Try changes as the Mac app

```bash
bin/dev              # "Survival LLM Dev": the Mac app running the code in this folder (restarts it if it's open)
bin/dev --fresh      # the same, as a brand-new person sees it: no library, memory, files or settings
bin/dev --release    # build the Mac app exactly as it ships (packaging/build.sh mac) and run that build
bin/dev stop         # quit it; bin/dev reset deletes its settings, memory and files; bin/dev log follows its log
```

Survival LLM Dev is built once into `~/Applications` (`--rebuild` builds it again) with the same Python, pywebview and
Ollama as the real app, but its code is a link to this folder, so every start runs the code as it is then; Spotlight
opens it too. It keeps its own settings, memory and files in `~/Library/Application Support/Survival LLM Dev`, so an
installed Survival LLM is left alone, and it shares the library and the AI models. A Dev badge and the line at the
bottom of the window name the branch and commit it runs, and it never updates itself. Its log is
`~/Library/Logs/Survival LLM Dev.log`.

## Build the library

```bash
python3 -m venv .venv && .venv/bin/pip install libzim lxml trafilatura
python3 library/fetch_zims.py        # Kiwix ZIM sources (about 50 GB, temporary)
python3 library/fetch_manuals.py     # U.S. government, IFRC and WHO manuals
.venv/bin/python library/fetch_risk.py   # risk references (death-rate statistics, micromort articles)
python3 library/fetch_agorismewiki.py    # the Dutch Agorisme wiki (personal builds only: it states no license)
curl -L -o library.noindex/raw/wikihowAll.csv \
  https://huggingface.co/datasets/Lajvi/wikihowAll/resolve/main/wikihowAll.csv   # wikiHow (620 MB)
.venv/bin/python library/build_library.py      # plain text + index in library.noindex/
```

`build_library.py` is incremental (finished sources are skipped) and `--rebuild KEY ...` redoes sources.
It needs `pdftotext` (poppler) for the PDF manuals.

**A default build is for your own use only:** it includes material that may not be shared (see SOURCES.md).
To build the shareable downloads:

```bash
LIBRARY_OUT=dist/library-full .venv/bin/python library/build_library.py --public
LIBRARY_OUT=dist/library-lite .venv/bin/python library/build_library.py --lite
python3 packaging/make_packs.py --base-url https://github.com/OWNER/survival-llm/releases/download/vX.Y.Z \
  lite=dist/library-lite full=dist/library-full   # parts for the release + library-packs.json for docs/
```

Packs carry a date (`--version`, default today); installed copies offer a pack with a newer date as an update.

## Package the apps

```bash
packaging/build.sh     # dist/Survival-LLM-mac.zip and dist/Survival-LLM-windows.zip (needs Xcode's command-line tools)
gh release create "v$(cat packaging/VERSION)" dist/Survival-LLM-mac.zip dist/Survival-LLM-windows.zip
python3 packaging/make_update.py "What's new" "..."   # writes docs/update.json; publish docs/ afterwards
```

Set the version in `packaging/VERSION` first. Installed copies read `docs/update.json` from the project's web page,
download the zip for their system, check its size and SHA-256, and replace themselves with it.

The Mac app bundles a portable Python, pywebview for its window, and Ollama. The Windows app bundles Python and
pywebview and downloads Ollama on first use (it is 1.6 GB with its graphics-card libraries).

## License

Code: MIT ([LICENSE](LICENSE)). Library content keeps the license of its source ([SOURCES.md](SOURCES.md)).

AI models make mistakes. Every answer shows its sources so you can check.
