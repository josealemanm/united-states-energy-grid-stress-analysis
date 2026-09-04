> **This is a tutorial, not documentation.**
>
> It walks through building this project from scratch on a Windows machine,
> and it was written before the code existed. It is not the reference for the
> current repo: the code in `src/` is the reference, and it has diverged from
> this tutorial in several places. The project now also has naive baseline
> forecasts, bootstrap confidence intervals, a second ramp-based stress
> definition, an HTML dashboard, and a rebuilt Power BI report. Read this
> for the reasoning and the click-by-click Power BI and Excel steps, not
> for the current numbers.

# United States Energy Grid Stress Analysis
## Complete Build Guide

**Author:** Jose Aleman
**Stack:** Python (pandas, requests) / SQL (DuckDB) / Power BI / Excel
**Data source:** U.S. Energy Information Administration, Form EIA-930, via EIA API v2
**Target build time:** 8 to 10 focused hours, plus a second sitting for the memo
**Guide revision:** 6, Windows-only, expanded click-by-click Excel and Power BI instructions, sourced cost figures, GitHub save-and-resume workflow in Parts 2.3 and 2.4

---

# TABLE OF CONTENTS

- Part 0: The question you are answering
- Part 1: Prerequisites and installation
- Part 2: Folder structure
- Part 3: Get your EIA API key
- Part 4: Understand the data before you pull it
- Part 5: Phase 1, the pull script (Python)
- Part 6: Phase 2, the validation script (Python)
- Part 7: Phase 3, the warehouse build (SQL)
- Part 8: Phase 4, the Excel assumptions register
- Part 9: Phase 5, Power BI data model
- Part 10: Phase 6, DAX measures
- Part 11: Phase 7, dashboard pages
- Part 12: Phase 8, the analyst memo
- Part 13: Finishing the GitHub repository and README
- Part 14: Resume bullets and interview prep
- Part 15: Troubleshooting
- Appendix A: Balancing authority reference
- Appendix B: Fuel type codes
- Appendix C: Glossary
- Appendix D: Build checklist

---

# PART 0: THE QUESTION YOU ARE ANSWERING

## 0.1 Do not skip this part

The most common way a portfolio project fails is starting with the data instead of
the question. You end up with twelve charts and no point. Read this section before
you write a single line of code, and keep the question visible while you build.

## 0.2 The question

> **When the U.S. power grid is under the most stress, does the day-ahead demand
> forecast get worse exactly when accuracy matters most, and which regions are most
> exposed?**

## 0.3 Why this is a real question

Every balancing authority publishes a day-ahead demand forecast (DF) and then
reports what demand actually turned out to be (D). The gap between them is
forecast error, and it is not free. When actual demand runs above forecast, the
operator buys the shortfall on the real time market at whatever it costs in that
hour, which is usually far above the day-ahead price. When actual demand runs
below forecast, generation was committed that did not need to be, and somebody
paid for it.

The interesting part is the interaction. Forecast error during a mild Tuesday in
April costs very little. Forecast error during the top 1 percent demand hour of a
July heat wave, when the marginal generator is an expensive gas peaker and the
region is importing at its limit, is a completely different number.

So the hypothesis worth testing is:

> **Forecast error is not uniformly distributed. It concentrates in the hours where
> it is most expensive, and the degree of concentration varies by region.**

If that is true, it has an operational implication: forecasting investment should
be targeted at stress hours in specific regions rather than spread evenly. That is
a recommendation. Recommendations are what get you hired.

## 0.4 What makes this a business analyst project and not a science fair project

Four things, and you must hit all four:

1. **There is a decision at the end.** You rank regions by exposure and say where
   to spend first. Not "here is a dashboard," but "here is where to act."
2. **The assumptions are explicit and sourced.** Especially the cost figure.
   You do not invent a dollar per megawatt hour. You take a documented range and
   run sensitivity on it.
3. **The data quality work is visible.** You will find bad rows. Showing what you
   found and how you handled it is worth more than a prettier chart.
4. **A non technical person can read the answer in ninety seconds.** That is the
   memo, and it is the part almost nobody does.

## 0.5 Scope guardrails

You will be tempted to expand this. Do not. Locked scope:

| Dimension | Locked value |
|---|---|
| Balancing authorities | 8 (listed in Part 4) |
| Time window | 24 months ending at the most recent complete month |
| Grain | One row per balancing authority per hour |
| Metrics pulled | D, DF, NG, TI, plus generation by fuel type |
| Deliverables | Repo, Power BI file, one page memo |

Anything else goes in a "future work" line at the bottom of the memo. That line
makes you look disciplined. Actually building those things makes you look unable
to finish.

---

# PART 1: PREREQUISITES AND INSTALLATION

## 1.0 Two kinds of gray box in this guide, and how to tell them apart

This guide contains two different things that both happen to sit in gray boxes,
and mixing them up is the single most common way to get stuck.

**Boxes labeled `powershell`** are commands. Type or paste these directly into
your PowerShell window and press Enter. They start doing something immediately.

**Every other labeled box** (`python`, `sql`, `gitignore`, `markdown`, `dax`,
plain text with no label) is **file content**, not a command. It is text that
belongs saved inside a file. If you paste one of these into PowerShell, it will
try to run each line as a command and fail with a wall of red text, usually
`... is not recognized as the name of a cmdlet`. That error means you pasted
content where a command belonged, not that anything is broken.

For every file this guide asks you to create, one of two things will happen:

1. **The instruction gives you one self-contained `powershell` command** that
   writes the whole file for you. Run that command as-is. Nothing to paste
   separately. This is how `.gitignore` and `.env` work below.
2. **The instruction says to open the file in VS Code and paste the content
   in.** This is how the longer files work, like `src/01_pull.py`. In that
   case: create and open the file with `code <path>` in PowerShell, paste the
   labeled block into the VS Code editor tab that opens, save with `Ctrl+S`,
   then return to PowerShell to run it.

If you are ever unsure which one you are looking at, check the label on the box.
`powershell` goes in the terminal. Anything else goes in a file.

## 1.1 What you need

**This guide is written for Windows 10 or Windows 11. Every command is
PowerShell.**

| Tool | Version | Cost | Where to get it |
|---|---|---|---|
| Windows | 10 or 11 | | 64 bit required for Power BI |
| Python | 3.10 or newer | Free | python.org, or `winget install Python.Python.3.12` |
| Power BI Desktop | Latest | Free | Microsoft Store (recommended, auto updates) |
| Excel | Any recent | You have it | Microsoft 365 fine |
| Git for Windows | Any | Free | git-scm.com, or `winget install Git.Git` |
| GitHub CLI | Latest | Free | `winget install GitHub.cli`. Handles GitHub login and repo creation. |
| Windows Terminal | Latest | Free | Microsoft Store. Much better than the old console. |
| VS Code | Latest | Free | Optional but recommended |

### Install everything with winget

Open **PowerShell** from the Start menu and run:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install GitHub.cli
winget install Microsoft.VisualStudioCode
winget install Microsoft.WindowsTerminal
```

Get Power BI Desktop from the Microsoft Store rather than the standalone
installer. The Store version updates itself, and Power BI ships monthly changes.

**Close and reopen PowerShell after installing Python.** The installer edits your
PATH and an already open window will not see it. This is the most common reason
`python` is "not recognized" right after an install.

### Confirm Python is on PATH

```powershell
python --version
```

If you get "Python was not found" and it opens the Microsoft Store, Windows is
routing you to an App Execution Alias. Fix it: **Settings**, **Apps**,
**Advanced app settings**, **App execution aliases**, and turn off both
`python.exe` and `python3.exe` entries. Then reopen PowerShell.

Note that on Windows the command is `python`, not `python3`. Every command in
this guide uses `python`.

Do not substitute Tableau. You said Power BI, business analyst postings say
Power BI, build Power BI.

## 1.2 Pin the project location, then install Python packages

**This guide fixes your project at one exact location, decided once, right
now:** `$HOME\grid-stress-dashboard`. `$HOME` is a variable PowerShell already
knows, it always resolves to your own Windows user folder automatically, so
this works without you having to know or type your actual username. Every `cd`
and every path in the rest of this guide refers back to this one location.
Nothing here is a placeholder you need to edit.

Open **PowerShell** and run this to create that folder and step inside it:

```powershell
New-Item -ItemType Directory -Path "$HOME\grid-stress-dashboard" -Force | Out-Null
Set-Location "$HOME\grid-stress-dashboard"
```

Confirm you are standing in the right place:

```powershell
Get-Location
```

That should print `$HOME\grid-stress-dashboard` with your actual username
filled in, something like `C:\Users\jalem\grid-stress-dashboard`. **This is
now your project root for the rest of the guide.** Part 2 builds the
subfolders inside it.

Now create the virtual environment. It must be created from inside this
folder, so the venv lives with the project rather than somewhere unrelated:

```powershell
# Create a project virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install everything you need
pip install requests pandas numpy pyarrow duckdb python-dotenv tqdm tabulate
```

What each package does:

| Package | Purpose |
|---|---|
| `requests` | Calls the EIA API |
| `pandas` | Reshapes the data |
| `pyarrow` | Writes parquet files (the format Power BI will read) |
| `duckdb` | The SQL engine, runs in process with no server |
| `numpy` | Numeric operations in the validation script |
| `python-dotenv` | Keeps your API key out of your source code |
| `tqdm` | Progress bars, so you can see the pull is alive |
| `tabulate` | Lets pandas render the data-quality tables as Markdown |

### If activation is blocked

PowerShell blocks unsigned scripts by default, so `Activate.ps1` may fail with a
message about execution policies. Fix it for your own account only:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Answer `Y`, then run the activation line again. `RemoteSigned` at
`CurrentUser` scope is the standard developer setting. Do not use `Bypass`, and
do not set it machine wide.

You will know activation worked when your prompt is prefixed with `(.venv)`.
**Every PowerShell window you open needs this activation again.** See Part 1.3
right below for the two commands you will run at the start of every session.

## 1.3 Resuming work after closing PowerShell

Closing a terminal tab does not delete anything. Every file you saved, every
row you pulled, and everything in git is still on disk exactly as you left it.
What you lose is only the *state of that window*: which folder it was sitting
in, and whether the virtual environment was active.

So every time you come back to this project, in a brand new PowerShell window,
run these two commands before anything else:

```powershell
Set-Location "$HOME\grid-stress-dashboard"
.venv\Scripts\Activate.ps1
```

Nothing to substitute here. `$HOME` resolves to your Windows user folder
automatically on any machine, so this is the exact same command every time.

If you ever genuinely lose track of where the folder is, for example you moved
it, this will search your whole user folder and print its real location:

```powershell
Get-ChildItem -Path $HOME -Recurse -Directory -Filter "grid-stress-dashboard" -ErrorAction SilentlyContinue | Select-Object FullName
```

You will know both commands worked when your prompt looks like this, with the
project folder name at the end:

```
(.venv) PS C:\Users\yourname\grid-stress-dashboard>
```

If it just says `PS C:\Users\jalem>` with no `(.venv)` prefix, the environment
is not active yet and `pip`-installed packages like pandas or duckdb will fail
to import. Run the two commands above again.

**This is the only setup you repeat.** Your `.env` file, your `.gitignore`,
your scripts, and any data you already pulled are untouched. You are not
starting over, you are only telling this new window where the project lives.

> Once you have set up GitHub in Part 2.3, the fuller resume routine adds
> `git pull` and `code .` to these two lines. See Part 2.4 for the complete
> close-and-resume habit, which is how you save progress and pick it up later
> without losing your place.

> If you closed VS Code as well and want your script files back open, use
> `code .` from inside the activated project folder. That opens the whole
> project as a VS Code workspace, with the file tree on the left, rather than
> reopening one file at a time.

## 1.4 Verify the install

```powershell
python -c "import requests, pandas, duckdb, pyarrow; print('all good')"
```

If that prints `all good`, you are ready.

---

# PART 2: FOLDER STRUCTURE

Create this exact structure. It matters, because a recruiter who opens your repo
forms an opinion in about four seconds, and a tidy tree is most of that opinion.

```
grid-stress-dashboard/          <- $HOME\grid-stress-dashboard. Fixed in Part 1.2.
│
├── .venv/                        <- Virtual environment. Created in Part 1.2.
├── README.md                     <- The first thing anyone reads
├── .gitignore                    <- Keeps secrets and big files out of git
├── .env                          <- YOUR API KEY. Never committed.
├── requirements.txt              <- Reproducibility
│
├── src/
│   ├── 00_smoke_test.py         <- Confirms the API key works
│   ├── 01_pull.py                <- Hits the EIA API, writes raw parquet
│   ├── 02_validate.py            <- Data quality checks, writes a report
│   ├── 03_build_warehouse.sql    <- Star schema in SQL
│   ├── 04_export_for_bi.py       <- Runs the SQL, exports parquet for Power BI
│   ├── query.py                  <- Runs ad-hoc SQL from scratch.sql
│   └── scratch.sql               <- Your SQL scratchpad for spot checks
│
├── data/
│   ├── raw/                      <- Untouched API output. Never edit by hand.
│   ├── interim/                  <- The DuckDB file lives here
│   └── processed/                <- Star schema parquet files for Power BI
│
├── reports/
│   ├── data_quality_report.md    <- Auto generated by 02_validate.py
│   ├── assumptions.xlsx          <- Your Excel assumptions register
│   └── memo.pdf                  <- The one page analyst memo
│
├── powerbi/
│   └── grid_stress.pbix          <- The dashboard
│
└── docs/
    └── screenshots/              <- Dashboard images for the README
```

## 2.1 Create the subfolders

You already created the project root and stepped inside it back in Part 1.2.
Confirm you are still there before continuing:

```powershell
Get-Location
```

That should show your `grid-stress-dashboard` folder. If it shows anything
else, run `Set-Location "$HOME\grid-stress-dashboard"` first. Everything below
assumes you are standing inside the project root, never outside it.

Now add the subfolders:

```powershell
$dirs = @(
    "src",
    "data\raw", "data\interim", "data\processed",
    "reports", "powerbi", "docs\screenshots"
)

foreach ($d in $dirs) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

# Confirm it worked
Get-ChildItem -Recurse -Directory | Select-Object FullName
```

`| Out-Null` suppresses the object output PowerShell would otherwise print for
every folder. Without it you get a wall of text that hides any actual error.

## 2.2 Write the .gitignore immediately

Do this **before** your first commit.

Run this entire block as **one paste** into PowerShell. It is a single command
using a here-string (the `@'` ... `'@` wrapper), which writes everything between
those markers into the file in one shot. Do not run the lines inside it one at a
time, and do not type just the word `.gitignore` on its own line, since
PowerShell will try to execute that as a command and fail.

```powershell
@'
# Secrets
.env

# Python
.venv/
__pycache__/
*.pyc

# Data (too big for git, and regenerable from the scripts)
data/raw/*
data/interim/*
data/processed/*
!data/raw/.gitkeep
!data/interim/.gitkeep
!data/processed/.gitkeep

# Power BI temp files
*.pbix.bak

# OS noise
.DS_Store
Thumbs.db
'@ | Set-Content -Path .gitignore -Encoding ascii
```

Confirm it worked:

```powershell
Get-ChildItem -Force .gitignore
Get-Content .gitignore
```

You should see the file listed and its contents printed back. If nothing
prints, the file was not created; check you are still in the
`grid-stress-dashboard` folder with `Get-Location`.

Then create the keep files so the empty folders still show up in the repo.
Windows has no `touch`, so use `New-Item`:

```powershell
"data\raw", "data\interim", "data\processed" | ForEach-Object {
    New-Item -ItemType File -Path "$_\.gitkeep" -Force | Out-Null
}
```

> **Watch out for Notepad.** If you ever create `.gitignore` or `.env` in
> Notepad using Save As, Windows will silently append `.txt` and you will end
> up with `.gitignore.txt`, which git ignores completely. The here-string
> command above avoids this entirely, since it never touches Notepad. Verify
> the name is exactly right with `Get-ChildItem -Force` (the `-Force` flag is
> what reveals files starting with a dot).

> **Why this matters for hiring:** committing a 400 MB data folder or a live API
> key to a public repo is the single most common junior mistake. Getting it right
> is a quiet signal that you have done this before.

## 2.3 Put this on GitHub now, before you write any code

Set up version control at the start, not the end. Two reasons. First, it becomes
your save system: after each work session you push, and your progress is safely
in the cloud where closing a laptop can never lose it. Second, committing as you
go produces an honest build history, which looks far better to a recruiter than
one commit called "final" dumped at the end.

You already wrote the `.gitignore` in Part 2.2, so your API key and data folders
are protected before the first commit ever happens. Good. Now:

### Step 1: turn this folder into a git repository

Make sure you are in the project root (`Get-Location` should show
`grid-stress-dashboard`), then:

```powershell
git init -b main
```

`-b main` names the default branch `main`, matching what GitHub expects.

### Step 2: tell git who you are

Git stamps every commit with a name and email. Set them once (this is global, so
you never do it again on this machine). Use the email tied to your GitHub
account:

```powershell
git config --global user.name "Jose Aleman"
git config --global user.email "josealemanmont@gmail.com"
```

### Step 3: log in to GitHub from the terminal

This is the step that trips people up, because GitHub no longer accepts your
account password over the command line. The GitHub CLI you installed in Part 1
handles it cleanly. Run:

```powershell
gh auth login
```

It asks a short series of questions. Answer them with the arrow keys and Enter:

- **What account?** GitHub.com
- **Preferred protocol?** HTTPS
- **Authenticate Git with your GitHub credentials?** Yes
- **How to authenticate?** Login with a web browser

It then shows a one-time code and opens your browser. Paste the code there, click
authorize, and return to PowerShell. You are now logged in, and git can push
without ever asking for a password. If you do not yet have a GitHub account,
create a free one at github.com first, then run the command.

### Step 4: make your first commit

```powershell
git add -A
git commit -m "Initial project structure with gitignore"
```

`git add -A` stages everything not excluded by `.gitignore`. If this stages
anything inside `data/` or your `.env`, stop, because your `.gitignore` is not
working. Check it with `git status` before continuing. You should see the
folder scaffolding and `.gitignore`, but never `.env` and never data files.

### Step 5: create the GitHub repository and push

The CLI can create the remote repo and push in one command. From the project
root:

```powershell
gh repo create grid-stress-dashboard --public --source . --remote origin --push
```

That creates a public repository named `grid-stress-dashboard` under your
account, links it to this folder as the remote named `origin`, and pushes your
first commit. When it finishes it prints the repository URL. Open that URL in
your browser and you should see your files.

> **Keep it private until it is presentable if you prefer.** Swap `--public` for
> `--private`. You can flip it to public later from the repo's settings page, or
> with `gh repo edit --visibility public`. An empty scaffold on a public profile
> is fine, but if it makes you uncomfortable, start private.

### From here on: the save habit

Every time you finish a chunk of work, save it to GitHub with the same three
commands. This is the loop you will run dozens of times:

```powershell
git add -A
git commit -m "Add the pull script and raw data extraction"
git push
```

Write a real message each time describing what you just did, not "update." Part
13 lists good example messages. The full pause-and-resume routine, so you can
close everything and pick up cleanly later, is in Part 2.4 right below.

## 2.4 The close-and-resume routine

This is the answer to "how do I stop for the day and pick up later without
losing my place." Two short routines.

**When you stop working (pause):**

```powershell
git add -A
git commit -m "describe what you just finished"
git push
```

That is it. Your work is now on GitHub. You can close VS Code, close PowerShell,
and shut down the machine. Nothing is lost, because everything is committed and
pushed.

**When you come back (resume):** open a fresh PowerShell window and run:

```powershell
Set-Location "$HOME\grid-stress-dashboard"
.venv\Scripts\Activate.ps1
git pull
code .
```

Line by line: step into the project, reactivate the Python environment (see Part
1.3), pull anything that changed (relevant if you ever work from a second
machine), and reopen the whole project in VS Code. Your prompt should show
`(.venv)` and you are exactly where you left off.

> **Working from a different computer later?** Because everything is on GitHub,
> on any Windows machine with the Part 1 tools installed you can run
> `gh repo clone grid-stress-dashboard` to pull the whole project down, then do
> the Part 1.2 environment setup (`python -m venv .venv`, activate,
> `pip install -r requirements.txt`). Your code and history come with you. The
> raw data does not, because `.gitignore` excludes it, but `python src\01_pull.py`
> regenerates it from the API. That is exactly why the pull is a script and not a
> one-time manual download.

---

# PART 3: GET YOUR EIA API KEY

## 3.1 Registration

1. Go to `https://www.eia.gov/opendata/`
2. Click the registration link for an API key.
3. Enter your name and email. Use your UMD address.
4. The key arrives by email within a minute or two. It is a long alphanumeric
   string.

It is free, there is no approval queue, and there is no cost tier.

## 3.2 Store it correctly

Run this single command in PowerShell. It both creates the file and writes
your key into it, replace the placeholder with your real key first:

```powershell
Set-Content -Path .env -Value "EIA_API_KEY=paste_your_key_here" -Encoding ascii
```

That is the only command for this step. **Do not separately type or paste
`EIA_API_KEY=...` into PowerShell on its own.** It is not a command, it is
what ends up inside the file, and the line above already puts it there for you.
If you do paste it on its own by mistake, PowerShell will report it as an
unrecognized command; that error is harmless, just re-run the line above and
move on.

Once it has run, the file's contents will read, with no quotes and no spaces
around the equals sign:

```
EIA_API_KEY=paste_your_key_here
```

(with your actual key in place of the placeholder). You can check this
yourself with the verification commands below.

Two Windows specific traps:

1. **Do not use `>` redirection.** `"EIA_API_KEY=x" > .env` writes UTF-16 with a
   byte order mark, and `python-dotenv` will read your key name as garbage.
   `Set-Content -Encoding ascii` avoids this.
2. **Do not create it in Notepad via Save As.** Windows appends `.txt` and you
   end up with `.env.txt`, which nothing will read.

Verify the file is right:

```powershell
Get-ChildItem -Force .env          # confirms the name is exactly ".env"
Get-Content .env                   # confirms the contents
```

Confirm `.env` is listed in your `.gitignore` before you commit anything.

## 3.3 Smoke test the key

Before writing the full pull script, prove the key works. This is the first
script file you create, so here is the pattern you will use for every script
from now on: create and open the file from PowerShell, then paste the content
into the VS Code tab that opens. The content goes in the **editor**, never in
the PowerShell prompt.

```powershell
code src\00_smoke_test.py
```

A VS Code tab opens with an empty file. Paste the block below into it and save
with `Ctrl+S`:

```python
"""Minimal check that the EIA API key works and the route is correct."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")

if not API_KEY:
    raise SystemExit("No EIA_API_KEY found. Check your .env file.")

url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
params = [
    ("api_key", API_KEY),
    ("frequency", "hourly"),
    ("data[0]", "value"),
    ("facets[respondent][]", "PJM"),
    ("facets[type][]", "D"),
    ("start", "2026-01-01T00"),
    ("end", "2026-01-02T00"),
    ("sort[0][column]", "period"),
    ("sort[0][direction]", "asc"),
    ("offset", 0),
    ("length", 5),
]

r = requests.get(url, params=params, timeout=30)
print("HTTP status:", r.status_code)
payload = r.json()

if "response" not in payload:
    print("Unexpected payload:", payload)
    raise SystemExit("Check your key and the route.")

print("Total rows available:", payload["response"].get("total"))
for row in payload["response"]["data"]:
    print(row)
```

Run it:

```powershell
python src\00_smoke_test.py
```

You should see HTTP status 200, a total row count, and five rows that look like:

```
{'period': '2026-01-01T00', 'respondent': 'PJM', 'respondent-name': 'PJM Interconnection, LLC',
 'type': 'D', 'type-name': 'Demand', 'value': 96432, 'value-units': 'megawatthours'}
```

If you get a 403, your key is wrong or has a stray quote or space in the `.env`
file. If you get a 404, the route string is wrong. Compare it character by
character against the URL above.

---

# PART 4: UNDERSTAND THE DATA BEFORE YOU PULL IT

## 4.1 What Form EIA-930 is

EIA-930 is the hourly reporting form that every balancing authority in the lower
48 files with the federal government. It was the first hourly data collection ever
run by a federal statistical agency, and it covers actual and forecast demand, net
generation, and the power flowing between systems for the balancing authorities
that make up the U.S. grid.

That last point is why this project works. The data is collected in a consistent
format from a single source across the whole country, so cross region comparison
is legitimate rather than an apples to oranges exercise you have to apologize for.

## 4.2 The API shape

**Base URL:** `https://api.eia.gov/v2/`

**Routes you will use:**

| Route | What it gives you |
|---|---|
| `electricity/rto/region-data/data/` | Demand, forecast, net generation, interchange, by BA and hour |
| `electricity/rto/fuel-type-data/data/` | Net generation split by fuel, by BA and hour |
| `electricity/rto/interchange-data/data/` | Directed flows between BA pairs (optional stretch) |

**Query parameters:**

| Parameter | Value | Notes |
|---|---|---|
| `api_key` | Your key | |
| `frequency` | `hourly` | UTC timestamps. `local-hourly` also exists. |
| `data[0]` | `value` | The measure column |
| `facets[respondent][]` | e.g. `PJM` | Repeatable for multiple BAs |
| `facets[type][]` | `D`, `DF`, `NG`, `TI` | Repeatable |
| `start` / `end` | `2024-08-01T00` | Format is `YYYY-MM-DDTHH` |
| `sort[0][column]` | `period` | Always sort, so pagination is stable |
| `sort[0][direction]` | `asc` | |
| `offset` | integer | Pagination cursor |
| `length` | `5000` | This is the maximum per request |

## 4.3 The four type codes (memorize these)

| Code | Meaning | Sign convention |
|---|---|---|
| `D` | Actual demand | Always positive |
| `DF` | Day ahead demand forecast | Always positive |
| `NG` | Net generation | Usually positive |
| `TI` | Total interchange | **Positive means net exporter** |

The form instructions define DF as the day ahead demand forecast and D as actual
demand, both of which should always be positive.

## 4.4 The balance identity (this is your secret weapon)

For any balancing authority in any hour, the physics requires:

```
Net Generation  minus  Total Interchange  equals  Demand

        NG      -           TI           =        D
```

Power generated, minus power sent to neighbors, equals power consumed locally.

**In the raw data, this identity frequently does not hold.** Meters disagree,
reporting lags, and values get estimated. EIA publishes both raw and adjusted
series partly for this reason.

You are going to measure the size of that imbalance per balancing authority and
report it. This single check will separate your project from every other student
dashboard, because it proves you understand what the numbers mean rather than
just how to chart them.

Define:

```
imbalance_mw = NG - TI - D
```

and track its magnitude as a percentage of demand. A BA with a 0.2 percent typical
imbalance is reporting cleanly. A BA with a 4 percent imbalance has a data quality
problem you should mention before you draw conclusions about it.

## 4.5 The eight balancing authorities

Locked list. Geographically spread, all large, all consistently reporting.

| Code | Name | Region | Local timezone | Why it is in the set |
|---|---|---|---|---|
| `PJM` | PJM Interconnection | Mid Atlantic | America/New_York | **Your grid.** Covers Maryland. |
| `MISO` | Midcontinent ISO | Midwest | America/New_York | Huge footprint, wind heavy |
| `CISO` | California ISO | West | America/Los_Angeles | The duck curve lives here |
| `ERCO` | ERCOT | Texas | America/Chicago | Isolated grid, famous failure mode |
| `ISNE` | ISO New England | Northeast | America/New_York | Winter peaking, gas constrained |
| `NYIS` | New York ISO | Northeast | America/New_York | Dense load, transmission limited |
| `SWPP` | Southwest Power Pool | Central | America/Chicago | Highest wind penetration |
| `SOCO` | Southern Company | Southeast | America/New_York | Summer peaking, nuclear heavy |

> **Known limitation, and you must state it in the memo:** MISO and SWPP each span
> more than one time zone. Assigning them a single local timezone is a
> simplification. Naming the limitation yourself is worth more than pretending it
> does not exist. An interviewer who spots it and finds it already documented
> concludes you are careful.

## 4.6 Expected data volume

Per balancing authority, over 24 months:

```
24 months  x  ~730 hours/month  =  ~17,520 hours
17,520 hours  x  4 type codes   =  ~70,080 rows per BA
70,080  x  8 BAs                =  ~560,000 rows (region data)
```

Plus fuel type data at roughly 8 fuels per BA hour, which lands near 1.1 million
rows.

**Total: roughly 1.7 million rows.**

That number matters. It is comfortably past the point where Excel pivot tables
become painful, which is exactly why the project justifies Python and SQL. When an
interviewer asks why you did not just use Excel, "1.7 million rows across two fact
tables" is the entire answer.

## 4.7 The stress hour definition

You need a defensible, documented definition of a stress hour. Use this one:

> **A stress hour is an hour whose actual demand falls in the top 5 percent of all
> hours for that balancing authority within that season.**

Three deliberate choices, and you should be able to defend each:

1. **Within balancing authority.** ERCOT's peak is far larger than ISNE's in
   absolute megawatts. Comparing raw MW across regions would just rank them by
   size. Percentile within BA makes regions comparable.
2. **Within season.** Without this, a summer peaking region would have all its
   stress hours in July and a winter peaking region all of them in January, and
   you would be measuring climate instead of stress.
3. **Top 5 percent.** Roughly 438 hours per BA per year. Enough for stable
   statistics, tight enough to mean something. Put the threshold in the Excel
   assumptions register and test 1 percent and 10 percent as sensitivity.

---

# PART 5: PHASE 1, THE PULL SCRIPT

**Time budget: 90 minutes to write and debug, 10 minutes to run.**

## 5.1 What this script does

1. Reads your API key from `.env`
2. Loops over the eight balancing authorities
3. For each one, pages through the API 5,000 rows at a time
4. Retries on transient failures with backoff
5. Writes raw parquet files, one per BA per dataset
6. Prints a summary so you know it worked

## 5.2 The script

Open VS Code and create the file with this PowerShell command, which both
makes the file and opens it for editing:

```powershell
code src\01_pull.py
```

A VS Code tab opens with an empty file. Paste the entire block below into
that tab, then save it with `Ctrl+S`. This is file content, not a command,
so it goes in the editor, never in the PowerShell prompt.

```python
"""
01_pull.py
Pull hourly EIA-930 grid operations data for eight U.S. balancing authorities.

Source: U.S. Energy Information Administration, API v2, Form EIA-930.
Writes one parquet file per balancing authority per dataset to data/raw/.

Run:  python src/01_pull.py
"""

import os
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
if not API_KEY:
    sys.exit("ERROR: no EIA_API_KEY in .env")

BASE_URL = "https://api.eia.gov/v2/"
PAGE_SIZE = 5000          # EIA maximum per request
MAX_RETRIES = 4
BACKOFF_SECONDS = 2       # doubles each retry
POLITE_DELAY = 0.25       # seconds between successful requests

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Eight balancing authorities. See Part 4.5 of the build guide.
RESPONDENTS = ["PJM", "MISO", "CISO", "ERCO", "ISNE", "NYIS", "SWPP", "SOCO"]

# Region data type codes: demand, day-ahead forecast, net generation, interchange
REGION_TYPES = ["D", "DF", "NG", "TI"]

# 24 month window ending at the start of the current month.
# EIA data lags by a day or two, so we never ask for the current month.
# timezone.utc keeps these timezone-aware; datetime.utcnow() is deprecated
# and prints a warning on Python 3.12+.
_today = datetime.now(timezone.utc)
END_DT = datetime(_today.year, _today.month, 1, tzinfo=timezone.utc)
START_DT = END_DT - timedelta(days=730)

START = START_DT.strftime("%Y-%m-%dT%H")
END = END_DT.strftime("%Y-%m-%dT%H")

print(f"Pull window: {START} to {END} (UTC)")


# ----------------------------------------------------------------------------
# CORE FETCH LOGIC
# ----------------------------------------------------------------------------

def fetch_page(route, base_params, offset):
    """Fetch a single page with retry and exponential backoff."""
    params = list(base_params) + [("offset", offset), ("length", PAGE_SIZE)]
    url = BASE_URL + route

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=60)

            if resp.status_code == 200:
                payload = resp.json()
                if "response" not in payload:
                    raise ValueError(f"Malformed payload: {str(payload)[:300]}")
                return payload["response"]

            # 429 is rate limiting, 5xx is server side. Both are worth retrying.
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_SECONDS * (2 ** attempt)
                print(f"  HTTP {resp.status_code}, retrying in {wait}s")
                time.sleep(wait)
                continue

            # 403 or 404 will not fix itself. Fail loudly.
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        except requests.exceptions.RequestException as exc:
            wait = BACKOFF_SECONDS * (2 ** attempt)
            print(f"  Network error ({exc}), retrying in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {route} offset {offset}")


def fetch_all(route, base_params, label):
    """Page through an entire result set and return a DataFrame."""
    first = fetch_page(route, base_params, offset=0)
    total = int(first.get("total", 0))

    if total == 0:
        print(f"  WARNING: {label} returned zero rows")
        return pd.DataFrame()

    rows = list(first["data"])
    n_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    for page in tqdm(range(1, n_pages), desc=f"  {label}", unit="page", leave=False):
        time.sleep(POLITE_DELAY)
        chunk = fetch_page(route, base_params, offset=page * PAGE_SIZE)
        rows.extend(chunk["data"])

    df = pd.DataFrame(rows)
    print(f"  {label}: {len(df):,} rows (API reported {total:,})")

    if len(df) != total:
        print(f"  WARNING: row count mismatch for {label}")

    return df


# ----------------------------------------------------------------------------
# DATASET BUILDERS
# ----------------------------------------------------------------------------

def pull_region_data(respondent):
    """Demand, forecast, net generation and interchange for one BA."""
    params = [
        ("api_key", API_KEY),
        ("frequency", "hourly"),
        ("data[0]", "value"),
        ("facets[respondent][]", respondent),
        ("start", START),
        ("end", END),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    for t in REGION_TYPES:
        params.append(("facets[type][]", t))

    return fetch_all("electricity/rto/region-data/data/", params, f"{respondent} region")


def pull_fuel_data(respondent):
    """Net generation by fuel type for one BA."""
    params = [
        ("api_key", API_KEY),
        ("frequency", "hourly"),
        ("data[0]", "value"),
        ("facets[respondent][]", respondent),
        ("start", START),
        ("end", END),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    return fetch_all("electricity/rto/fuel-type-data/data/", params, f"{respondent} fuel")


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    started = time.time()
    manifest = []

    for ba in RESPONDENTS:
        print(f"\n=== {ba} ===")

        region = pull_region_data(ba)
        if not region.empty:
            path = RAW_DIR / f"region_{ba}.parquet"
            region.to_parquet(path, index=False)
            manifest.append({"ba": ba, "dataset": "region", "rows": len(region)})

        fuel = pull_fuel_data(ba)
        if not fuel.empty:
            path = RAW_DIR / f"fuel_{ba}.parquet"
            fuel.to_parquet(path, index=False)
            manifest.append({"ba": ba, "dataset": "fuel", "rows": len(fuel)})

    # A manifest is how you prove later what you actually pulled and when.
    mf = pd.DataFrame(manifest)
    mf["pulled_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mf["window_start"] = START
    mf["window_end"] = END
    mf.to_csv(RAW_DIR / "_manifest.csv", index=False)

    elapsed = time.time() - started
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} minutes")
    print(f"Total rows: {mf['rows'].sum():,}")
    print(mf.groupby('dataset')['rows'].sum().to_string())
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

## 5.3 Run it

```powershell
python src\01_pull.py
```

Expect eight to twelve minutes. Go get coffee. When it finishes you should see
roughly 1.7 million total rows and sixteen parquet files plus a manifest in
`data/raw/`.

## 5.4 Three things in this script worth pointing out in an interview

**The manifest.** Writing down what you pulled, when, and over what window is
basic data provenance. When someone asks in November why your numbers do not
match the EIA website, the manifest is the answer.

**The retry with exponential backoff.** Anyone can write `requests.get`. Handling
429 and 5xx separately from 403 and 404 shows you know which failures are worth
retrying and which are your own fault.

**The row count assertion.** Comparing the rows you actually received against the
total the API reported catches silent pagination bugs, which are the nastiest
category because the data looks fine and is just quietly incomplete.

---

# PART 6: PHASE 2, THE VALIDATION SCRIPT

**Time budget: 60 minutes.**

## 6.1 Why this phase exists

You will find problems. Missing hours, duplicated timestamps, nulls, and
balance identity failures are all present in this data. Finding them is not a
setback, it is the deliverable. The validation report is a section of your memo
and a page of your dashboard.

## 6.2 The script

Same pattern as the last file: open and create it from PowerShell, then
paste the content into the VS Code tab that opens.

```powershell
code src\02_validate.py
```

```python
"""
02_validate.py
Data quality assessment of raw EIA-930 pulls.
Writes reports/data_quality_report.md and a machine readable CSV.

Run:  python src/02_validate.py
"""

from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path("data/raw")
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

RESPONDENTS = ["PJM", "MISO", "CISO", "ERCO", "ISNE", "NYIS", "SWPP", "SOCO"]


def load_region(ba):
    df = pd.read_parquet(RAW_DIR / f"region_{ba}.parquet")
    df["period"] = pd.to_datetime(df["period"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def wide_form(df):
    """Pivot the long type codes into one row per hour."""
    wide = df.pivot_table(
        index="period", columns="type", values="value", aggfunc="first"
    ).reset_index()
    for col in ["D", "DF", "NG", "TI"]:
        if col not in wide.columns:
            wide[col] = np.nan
    return wide


def check_ba(ba):
    raw = load_region(ba)
    wide = wide_form(raw)
    results = {"ba": ba}

    # --- Completeness ------------------------------------------------------
    span_start, span_end = wide["period"].min(), wide["period"].max()
    expected = pd.date_range(span_start, span_end, freq="h", tz="UTC")
    actual = set(wide["period"])
    missing = [h for h in expected if h not in actual]

    results["first_hour"] = span_start
    results["last_hour"] = span_end
    results["expected_hours"] = len(expected)
    results["actual_hours"] = len(actual)
    results["missing_hours"] = len(missing)
    results["pct_complete"] = round(100 * len(actual) / len(expected), 3)

    # --- Duplicates --------------------------------------------------------
    dupes = raw.duplicated(subset=["period", "type"]).sum()
    results["duplicate_rows"] = int(dupes)

    # --- Nulls -------------------------------------------------------------
    for col in ["D", "DF", "NG", "TI"]:
        results[f"null_{col}"] = int(wide[col].isna().sum())

    # --- Impossible values -------------------------------------------------
    # Demand and forecast must be positive per the EIA-930 form instructions.
    results["negative_D"] = int((wide["D"] < 0).sum())
    results["negative_DF"] = int((wide["DF"] < 0).sum())
    results["zero_D"] = int((wide["D"] == 0).sum())

    # --- Outliers (robust: median absolute deviation, not standard deviation)
    d = wide["D"].dropna()
    med = d.median()
    mad = (d - med).abs().median()
    if mad > 0:
        modified_z = 0.6745 * (d - med) / mad
        results["outlier_hours_D"] = int((modified_z.abs() > 6).sum())
    else:
        results["outlier_hours_D"] = 0

    # --- The balance identity: NG - TI should equal D ----------------------
    wide["imbalance_mw"] = wide["NG"] - wide["TI"] - wide["D"]
    wide["imbalance_pct"] = 100 * wide["imbalance_mw"] / wide["D"].replace(0, np.nan)

    results["median_abs_imbalance_pct"] = round(
        wide["imbalance_pct"].abs().median(), 3
    )
    results["p95_abs_imbalance_pct"] = round(
        wide["imbalance_pct"].abs().quantile(0.95), 3
    )
    results["hours_imbalance_over_5pct"] = int(
        (wide["imbalance_pct"].abs() > 5).sum()
    )

    # --- Headline forecast error (a preview of the real analysis) ----------
    wide["abs_pct_err"] = 100 * (wide["DF"] - wide["D"]).abs() / wide["D"].replace(0, np.nan)
    results["overall_MAPE"] = round(wide["abs_pct_err"].mean(), 3)

    return results


def main():
    rows = [check_ba(ba) for ba in RESPONDENTS]
    qa = pd.DataFrame(rows)
    qa.to_csv(REPORT_DIR / "data_quality_summary.csv", index=False)

    lines = [
        "# Data Quality Report",
        "",
        "Source: U.S. Energy Information Administration, Form EIA-930, API v2.",
        "Generated by `src/02_validate.py`.",
        "",
        "## Completeness",
        "",
        qa[["ba", "expected_hours", "actual_hours", "missing_hours",
            "pct_complete", "duplicate_rows"]].to_markdown(index=False),
        "",
        "## Null and impossible values",
        "",
        qa[["ba", "null_D", "null_DF", "null_NG", "null_TI",
            "negative_D", "zero_D", "outlier_hours_D"]].to_markdown(index=False),
        "",
        "## Balance identity check (NG - TI = D)",
        "",
        "The EIA-930 accounting identity requires net generation minus total",
        "interchange to equal demand. Deviation indicates measurement or",
        "reporting error. Values are the absolute deviation as a percent of demand.",
        "",
        qa[["ba", "median_abs_imbalance_pct", "p95_abs_imbalance_pct",
            "hours_imbalance_over_5pct"]].to_markdown(index=False),
        "",
        "## Headline forecast error",
        "",
        qa[["ba", "overall_MAPE"]].to_markdown(index=False),
        "",
        "## Handling decisions",
        "",
        "1. Hours missing any of D, DF, NG or TI are excluded from forecast",
        "   error statistics rather than interpolated. Interpolating a forecast",
        "   error would manufacture the exact quantity being measured.",
        "2. Hours where demand is zero or negative are dropped as impossible",
        "   per the EIA-930 form instructions.",
        "3. Balance identity failures are reported but not corrected. EIA",
        "   publishes adjusted series for this purpose; using raw values keeps",
        "   the provenance simple and the limitation visible.",
        "",
    ]

    (REPORT_DIR / "data_quality_report.md").write_text("\n".join(lines))
    print(qa.to_string(index=False))
    print("\nWrote reports/data_quality_report.md")


if __name__ == "__main__":
    main()
```

## 6.3 Run it and actually read the output

```powershell
python src\02_validate.py
```

Do not skim this. Look at which balancing authority has the worst balance
imbalance and the most missing hours. Those facts go in your memo, and they are
frequently more interesting than the headline result.

**Note the choice in handling decision 1.** Interpolating missing demand values
before computing forecast error would invent the thing you are measuring. Being
able to explain why you did not interpolate is a better interview answer than any
chart you will build.

---

# PART 7: PHASE 3, THE WAREHOUSE BUILD (SQL)

**Time budget: 2 hours. This is the most important phase.**

## 7.1 Why SQL and not more pandas

You could do all of this in pandas. Do it in SQL instead, for two reasons.

First, business analyst postings ask for SQL and your resume currently does not
claim it. After this project it can, honestly, backed by a repo someone can open.

Second, this is genuinely what SQL is for. Window functions partitioned by region
and season are the natural expression of "top 5 percent of hours within this
group," and writing that in pandas is clumsier.

DuckDB runs in process with no server to install, reads parquet directly, and
handles 1.7 million rows without noticing.

## 7.2 The star schema you are building

```
                    ┌──────────────┐
                    │   dim_date   │
                    │  date_key PK │
                    └──────┬───────┘
                           │
    ┌──────────────┐       │       ┌──────────────┐
    │    dim_ba    │       │       │   dim_fuel   │
    │  ba_code PK  │       │       │ fuel_code PK │
    └──────┬───────┘       │       └──────┬───────┘
           │               │              │
           │       ┌───────┴────────┐     │
           └───────┤ fact_grid_     │     │
                   │    hourly      │     │
                   │ (BA x hour)    │     │
                   └────────────────┘     │
           ┌───────────────────────┐      │
           └───────┤ fact_fuel_hourly ├───┘
                   │ (BA x hour x fuel)│
                   └───────────────────┘
```

**Grain statements.** Write these down, because an interviewer will ask.

- `fact_grid_hourly`: one row per balancing authority per UTC hour.
- `fact_fuel_hourly`: one row per balancing authority per UTC hour per fuel type.

## 7.3 The SQL

Open and create it the same way:

```powershell
code src\03_build_warehouse.sql
```

Paste the SQL below into the VS Code tab and save. This file is never run
directly. `04_export_for_bi.py`, which you will create next, reads this
file's text and executes it against DuckDB.

```sql
-- ===========================================================================
-- 03_build_warehouse.sql
-- Builds a star schema from raw EIA-930 parquet files.
-- Engine: DuckDB
-- Grain: fact_grid_hourly  = balancing authority x UTC hour
--        fact_fuel_hourly  = balancing authority x UTC hour x fuel type
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- DIMENSION: BALANCING AUTHORITY
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_ba AS
SELECT * FROM (VALUES
    ('PJM',  'PJM Interconnection',      'Mid Atlantic', 'Eastern',     'America/New_York',    TRUE),
    ('MISO', 'Midcontinent ISO',         'Midwest',      'Eastern',     'America/New_York',    FALSE),
    ('CISO', 'California ISO',           'West',         'Western',     'America/Los_Angeles', FALSE),
    ('ERCO', 'ERCOT',                    'Texas',        'Texas',       'America/Chicago',     FALSE),
    ('ISNE', 'ISO New England',          'Northeast',    'Eastern',     'America/New_York',    FALSE),
    ('NYIS', 'New York ISO',             'Northeast',    'Eastern',     'America/New_York',    FALSE),
    ('SWPP', 'Southwest Power Pool',     'Central',      'Eastern',     'America/Chicago',     FALSE),
    ('SOCO', 'Southern Company',         'Southeast',    'Eastern',     'America/New_York',    FALSE)
) AS t(ba_code, ba_name, region, interconnection, local_tz, is_home_grid);

-- NOTE: MISO and SWPP span multiple time zones. A single local_tz is a
-- documented simplification. See memo limitations section.


-- ---------------------------------------------------------------------------
-- DIMENSION: FUEL TYPE
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_fuel AS
SELECT * FROM (VALUES
    ('COL', 'Coal',          'Thermal',      FALSE, TRUE,  1),
    ('NG',  'Natural gas',   'Thermal',      FALSE, TRUE,  2),
    ('NUC', 'Nuclear',       'Thermal',      FALSE, FALSE, 3),
    ('OIL', 'Petroleum',     'Thermal',      FALSE, TRUE,  4),
    ('WAT', 'Hydro',         'Renewable',    TRUE,  TRUE,  5),
    ('SUN', 'Solar',         'Renewable',    TRUE,  FALSE, 6),
    ('WND', 'Wind',          'Renewable',    TRUE,  FALSE, 7),
    ('OTH', 'Other',         'Other',        FALSE, FALSE, 8),
    ('UNK', 'Unknown',       'Other',        FALSE, FALSE, 9)
) AS t(fuel_code, fuel_name, fuel_group, is_renewable, is_dispatchable, sort_order);

-- is_dispatchable: can the operator call on it at will? Solar and wind cannot
-- be dispatched up, which is the entire reason net load ramp matters.


-- ---------------------------------------------------------------------------
-- STAGING: pivot the long region data into one row per BA hour
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_region AS
SELECT
    respondent                                          AS ba_code,
    CAST(strptime(period, '%Y-%m-%dT%H') AS TIMESTAMP)  AS ts_utc,
    MAX(CASE WHEN type = 'D'  THEN CAST(value AS DOUBLE) END) AS demand_mw,
    MAX(CASE WHEN type = 'DF' THEN CAST(value AS DOUBLE) END) AS forecast_mw,
    MAX(CASE WHEN type = 'NG' THEN CAST(value AS DOUBLE) END) AS net_gen_mw,
    MAX(CASE WHEN type = 'TI' THEN CAST(value AS DOUBLE) END) AS interchange_mw
FROM read_parquet('data/raw/region_*.parquet')
GROUP BY 1, 2;


-- ---------------------------------------------------------------------------
-- STAGING: apply local time, season, and quality filters
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_region_enriched AS
SELECT
    s.ba_code,
    s.ts_utc,
    -- Convert UTC to local. The inner AT TIME ZONE declares that ts_utc IS UTC;
    -- the outer one converts that instant into local wall clock time. Applying
    -- AT TIME ZONE only once converts in the WRONG DIRECTION and silently shifts
    -- every hour by twice the offset. Verify against a known hour before trusting it.
    (s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz AS ts_local,
    s.demand_mw,
    s.forecast_mw,
    s.net_gen_mw,
    s.interchange_mw,

    -- Season is defined on LOCAL time, because load is driven by local weather.
    CASE
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (12,1,2) THEN 'Winter'
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (3,4,5)  THEN 'Spring'
        WHEN EXTRACT(month FROM ((s.ts_utc AT TIME ZONE 'UTC') AT TIME ZONE b.local_tz)) IN (6,7,8)  THEN 'Summer'
        ELSE 'Fall'
    END                                                 AS season,

    -- Balance identity residual. See Part 4.4.
    s.net_gen_mw - s.interchange_mw - s.demand_mw       AS imbalance_mw

FROM stg_region s
JOIN dim_ba b ON b.ba_code = s.ba_code
WHERE s.demand_mw  IS NOT NULL
  AND s.forecast_mw IS NOT NULL
  AND s.demand_mw  > 0;
-- Rows failing these conditions are excluded, not interpolated.
-- Rationale is documented in reports/data_quality_report.md.


-- ---------------------------------------------------------------------------
-- FACT: grid hourly
-- This is where the window functions do the real work.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_grid_hourly AS
WITH ranked AS (
    SELECT
        *,
        -- Demand percentile WITHIN balancing authority AND season.
        -- This is the stress hour definition from Part 4.7.
        PERCENT_RANK() OVER (
            PARTITION BY ba_code, season
            ORDER BY demand_mw
        ) AS demand_pctile,

        -- Hour over hour ramp. Large positive ramps are when operators sweat.
        demand_mw - LAG(demand_mw) OVER (
            PARTITION BY ba_code
            ORDER BY ts_utc
        ) AS ramp_1h_mw,

        -- Rolling 24 hour average demand, for context on any single hour.
        AVG(demand_mw) OVER (
            PARTITION BY ba_code
            ORDER BY ts_utc
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS demand_ma24_mw

    FROM stg_region_enriched
)
SELECT
    ba_code,
    ts_utc,
    ts_local,
    CAST(ts_local AS DATE)                              AS date_key,
    EXTRACT(hour FROM ts_local)                         AS hour_local,
    season,

    demand_mw,
    forecast_mw,
    net_gen_mw,
    interchange_mw,

    -- Positive interchange means the BA is a net EXPORTER, so imports are the
    -- negative of it. Flipping the sign here saves confusion downstream.
    -interchange_mw                                     AS net_import_mw,

    -- ---- Forecast error metrics ----
    forecast_mw - demand_mw                             AS forecast_error_mw,
    ABS(forecast_mw - demand_mw)                        AS abs_error_mw,
    100.0 * (forecast_mw - demand_mw) / demand_mw       AS pct_error,
    100.0 * ABS(forecast_mw - demand_mw) / demand_mw    AS abs_pct_error,

    -- Under forecasting is the expensive direction: actual exceeded forecast,
    -- so the shortfall had to be bought in the real time market.
    CASE WHEN forecast_mw < demand_mw
         THEN demand_mw - forecast_mw ELSE 0 END        AS shortfall_mw,

    -- ---- Stress classification ----
    demand_pctile,
    CASE WHEN demand_pctile >= 0.95 THEN TRUE ELSE FALSE END AS is_stress_hour,
    CASE WHEN demand_pctile >= 0.99 THEN TRUE ELSE FALSE END AS is_extreme_hour,

    ramp_1h_mw,
    demand_ma24_mw,
    imbalance_mw,
    100.0 * imbalance_mw / demand_mw                    AS imbalance_pct

FROM ranked;


-- ---------------------------------------------------------------------------
-- FACT: fuel hourly
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_fuel_hourly AS
SELECT
    f.respondent                                            AS ba_code,
    CAST(strptime(f.period, '%Y-%m-%dT%H') AS TIMESTAMP)    AS ts_utc,
    f.fueltype                                              AS fuel_code,
    CAST(f.value AS DOUBLE)                                 AS generation_mw
FROM read_parquet('data/raw/fuel_*.parquet') f
WHERE f.value IS NOT NULL;


-- ---------------------------------------------------------------------------
-- FACT ENRICHMENT: net load
-- Net load = demand minus the generation that cannot be dispatched.
-- This is the quantity dispatchable plants actually have to chase, and its
-- steepest ramps are the real operational constraint.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_grid_hourly AS
WITH vre AS (
    SELECT
        ba_code,
        ts_utc,
        SUM(CASE WHEN fuel_code = 'SUN' THEN generation_mw ELSE 0 END) AS solar_mw,
        SUM(CASE WHEN fuel_code = 'WND' THEN generation_mw ELSE 0 END) AS wind_mw
    FROM fact_fuel_hourly
    GROUP BY 1, 2
)
SELECT
    g.*,
    COALESCE(v.solar_mw, 0)                                  AS solar_mw,
    COALESCE(v.wind_mw, 0)                                   AS wind_mw,
    g.demand_mw - COALESCE(v.solar_mw,0) - COALESCE(v.wind_mw,0) AS net_load_mw,
    100.0 * (COALESCE(v.solar_mw,0) + COALESCE(v.wind_mw,0))
        / NULLIF(g.demand_mw, 0)                             AS vre_share_pct
FROM fact_grid_hourly g
LEFT JOIN vre v
  ON v.ba_code = g.ba_code AND v.ts_utc = g.ts_utc;


-- ---------------------------------------------------------------------------
-- DIMENSION: DATE
-- Built from the fact table so it always covers exactly the right span.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT MIN(date_key) AS d0, MAX(date_key) AS d1 FROM fact_grid_hourly
),
days AS (
    SELECT UNNEST(generate_series(
        (SELECT d0 FROM bounds),
        (SELECT d1 FROM bounds),
        INTERVAL 1 DAY
    )) AS d
)
SELECT
    CAST(d AS DATE)                                     AS date_key,
    EXTRACT(year   FROM d)                              AS year,
    EXTRACT(month  FROM d)                              AS month_num,
    strftime(d, '%B')                                   AS month_name,
    strftime(d, '%Y-%m')                                AS year_month,
    EXTRACT(quarter FROM d)                             AS quarter,
    EXTRACT(dow FROM d)                                 AS day_of_week_num,
    strftime(d, '%A')                                   AS day_name,
    CASE WHEN EXTRACT(dow FROM d) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
    CASE
        WHEN EXTRACT(month FROM d) IN (12,1,2) THEN 'Winter'
        WHEN EXTRACT(month FROM d) IN (3,4,5)  THEN 'Spring'
        WHEN EXTRACT(month FROM d) IN (6,7,8)  THEN 'Summer'
        ELSE 'Fall'
    END                                                 AS season
FROM days;


-- ---------------------------------------------------------------------------
-- THE HEADLINE ANALYSIS
-- Does forecast error get worse during stress hours?
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE analysis_stress_penalty AS
SELECT
    g.ba_code,
    b.ba_name,
    b.region,

    COUNT(*)                                                     AS total_hours,
    SUM(CASE WHEN is_stress_hour THEN 1 ELSE 0 END)              AS stress_hours,

    ROUND(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END), 3) AS mape_normal,
    ROUND(AVG(CASE WHEN is_stress_hour     THEN abs_pct_error END), 3) AS mape_stress,
    ROUND(AVG(CASE WHEN is_extreme_hour    THEN abs_pct_error END), 3) AS mape_extreme,

    -- The headline number: how much worse is the forecast when it matters?
    ROUND(
        AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
      - AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END)
    , 3)                                                         AS stress_penalty_pp,

    -- Ratio form, which is often the more quotable version.
    ROUND(
        AVG(CASE WHEN is_stress_hour THEN abs_pct_error END)
      / NULLIF(AVG(CASE WHEN NOT is_stress_hour THEN abs_pct_error END), 0)
    , 2)                                                         AS stress_multiple,

    -- Bias: positive means the forecast tends to run high.
    ROUND(AVG(CASE WHEN is_stress_hour THEN pct_error END), 3)   AS bias_stress_pct,

    -- Exposure context
    ROUND(AVG(CASE WHEN is_stress_hour THEN net_import_mw END), 0) AS avg_net_import_stress_mw,
    ROUND(MAX(ramp_1h_mw), 0)                                    AS max_1h_ramp_mw,
    ROUND(SUM(CASE WHEN is_stress_hour THEN shortfall_mw ELSE 0 END), 0) AS total_stress_shortfall_mwh

FROM fact_grid_hourly g
JOIN dim_ba b ON b.ba_code = g.ba_code
GROUP BY 1, 2, 3
ORDER BY stress_penalty_pp DESC;
```

## 7.4 The runner script

Last script file, same pattern:

```powershell
code src\04_export_for_bi.py
```

```python
"""
04_export_for_bi.py
Executes the warehouse SQL and exports star schema tables as parquet
for Power BI to consume.

Run:  python src/04_export_for_bi.py
"""

from pathlib import Path
import duckdb
import pandas as pd

DB_PATH = Path("data/interim/grid.duckdb")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_PATH))

sql = Path("src/03_build_warehouse.sql").read_text()
print("Building warehouse...")
con.execute(sql)

TABLES = [
    "dim_ba",
    "dim_fuel",
    "dim_date",
    "fact_grid_hourly",
    "fact_fuel_hourly",
    "analysis_stress_penalty",
]

for t in TABLES:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    # .as_posix() forces forward slashes. On Windows a Path renders as
    # data\processed\dim_ba.parquet, and embedding those backslashes in a SQL
    # string literal is fragile. Forward slashes work fine on Windows and
    # remove the whole class of problem.
    out_path = (OUT_DIR / f"{t}.parquet").as_posix()

    con.execute(f"COPY {t} TO '{out_path}' (FORMAT PARQUET)")
    print(f"  {t:28s} {n:>10,} rows")

# --- Optional CSV fallback ---------------------------------------------------
# If Power BI's Parquet connector gives you trouble (older versions), uncomment
# these three lines to also write CSVs, then load the CSVs into Power BI instead.
# Parquet is preferred because it carries data types; CSV will need a few column
# types fixed by hand in Power Query.
#
# for t in TABLES:
#     csv_path = (OUT_DIR / f"{t}.csv").as_posix()
#     con.execute(f"COPY {t} TO '{csv_path}' (FORMAT CSV, HEADER)")

print("\n" + "=" * 70)
print("HEADLINE RESULT: forecast error, stress hours vs normal hours")
print("=" * 70)
result = con.execute("""
    SELECT ba_code, region, mape_normal, mape_stress,
           stress_penalty_pp, stress_multiple
    FROM analysis_stress_penalty
    ORDER BY stress_penalty_pp DESC
""").df()
print(result.to_string(index=False))

con.close()
print(f"\nParquet written to {OUT_DIR}/")
```

Run it:

```powershell
python src\04_export_for_bi.py
```

**This is the moment of truth.** The printed table is your finding. Look at it
carefully before moving on.

## 7.5 A scratchpad for running your own SQL

Several later steps ask you to run a quick SQL query against the warehouse, to
verify something or find a specific row. You need a way to do that without the
pain of pasting SQL directly into PowerShell, where quotes and spaces cause
trouble. The clean way is a tiny helper that runs whatever SQL you put in a
file.

Create it once now:

```powershell
code src\query.py
```

Paste this into the VS Code tab and save:

```python
"""
query.py
Run whatever SQL is in src/scratch.sql against the built warehouse and print
the result. Edit src/scratch.sql, save it, then run:  python src/query.py

Keeping the query in a file avoids pasting SQL straight into PowerShell, where
quotes and spaces cause trouble.
"""

from pathlib import Path
import duckdb
import pandas as pd

pd.set_option("display.max_rows", 100)
pd.set_option("display.width", 200)

DB_PATH = Path("data/interim/grid.duckdb")
SQL_PATH = Path("src/scratch.sql")

if not DB_PATH.exists():
    raise SystemExit(
        "No warehouse at data/interim/grid.duckdb. Run 04_export_for_bi.py first."
    )

if not SQL_PATH.exists() or not SQL_PATH.read_text().strip():
    SQL_PATH.write_text("SELECT 'put your query here and re-run' AS message;\n")
    print("Created src/scratch.sql. Put a query in it and run again.")
    raise SystemExit(0)

# read_only=True means a scratch query can never damage the warehouse.
con = duckdb.connect(str(DB_PATH), read_only=True)
result = con.execute(SQL_PATH.read_text().strip()).df()
con.close()

print(result.to_string(index=False))
```

From now on, "run this query" means: paste the SQL into `src/scratch.sql` (open
it with `code src\scratch.sql`), save, then run `python src\query.py`. Each new
query replaces whatever was in the file before.

## 7.6 How to read your own result

| What you see | What it means | What to do |
|---|---|---|
| `stress_multiple` above 1.3 for most BAs | Hypothesis supported. Error concentrates where it is expensive. | Lead the memo with it. |
| `stress_multiple` near 1.0 across the board | Forecasts are robust under stress. | This is still a finding. Report it honestly and pivot the memo to which regions are outliers. |
| One BA wildly different | Either a real regional story or a data artifact. | Check its imbalance and missing hour stats first. |
| `stress_multiple` below 1.0 | Forecasts are BETTER at peak. Plausible, because operators pay more attention to peak days. | Say so. A result that contradicts your hypothesis and is honestly reported is more credible than one that confirms it. |

> **Important.** Do not adjust the analysis until it gives you the answer you
> wanted. Whatever it says is the finding. An analyst who reports an
> inconvenient result is worth more than one who produces a tidy story, and
> interviewers can tell the difference.

## 7.7 Verify the timezone conversion before you trust anything

This is the easiest place in the whole project to be silently wrong, so check it.
Paste this into `src/scratch.sql` (open it with `code src\scratch.sql`), save,
then run `python src\query.py`:

```sql
SELECT ba_code, hour_local, ROUND(AVG(demand_mw)) AS avg_demand
FROM fact_grid_hourly
WHERE season = 'Summer'
GROUP BY 1, 2
ORDER BY ba_code, hour_local;
```

Summer demand should peak in the late afternoon or early evening local time,
somewhere around hour 16 to 19, and bottom out in the small hours around 3 to 5.
If your peak lands at 3am, the conversion ran backwards and every hour is shifted
by twice the UTC offset.

The trap: in DuckDB, `AT TIME ZONE` applied to a naive `TIMESTAMP` treats that
timestamp as already being local in the named zone and converts it to UTC, which
is the opposite of what you want. Declaring UTC first with
`(ts_utc AT TIME ZONE 'UTC')` and then converting is what produces local wall
clock time. The SQL above does this correctly, but verify anyway, because a
silent eight hour shift would not throw an error. It would just quietly ruin your
hour of day chart and misassign some hours to the wrong season.

---

# PART 8: PHASE 4, THE EXCEL ASSUMPTIONS REGISTER

**Time budget: 45 minutes.**

## 8.1 Why Excel is in this project at all

Not as a crutch. Excel is where the **assumptions** live, and separating
assumptions from code is a real analyst discipline. When a manager asks "what if
the cost number were half that," you change one cell rather than editing a script.
This is also the tab you point to in an interview when someone asks "where do your
numbers come from," so it needs to look deliberate.

You are going to build one workbook, `reports/assumptions.xlsx`, with four tabs.
Everything below is click by click. If you have never built a structured
spreadsheet before, follow it literally the first time.

### Create the workbook

1. Open Excel. Click **Blank workbook**.
2. Press **Ctrl+S**. Navigate to your project's `reports` folder
   (`$HOME\grid-stress-dashboard\reports`), name the file `assumptions`, leave
   the type as **Excel Workbook (.xlsx)**, and click **Save**.
3. At the bottom left you will see one sheet tab called `Sheet1`. You need four
   tabs. Right click `Sheet1`, choose **Rename**, and type `Assumptions`. Press
   Enter.
4. Click the small **+** to the right of the tab three times to add three more
   sheets. Rename them `BA_Reference`, `Data_Quality`, and `Sensitivity` the same
   way. You should now have four tabs across the bottom.

## 8.2 Tab 1: `Assumptions`

Click the `Assumptions` tab. You are going to build a small input table. Type each
value into the exact cell listed. To move to a specific cell, click it, or type
its address (like `A1`) into the **Name Box**, the little box at the top left just
above column A, and press Enter.

First the headers. In row 2, type these four column titles:

- `A2`: `Parameter`
- `B2`: `Value`
- `C2`: `Unit`
- `D2`: `Source / rationale`

Then fill in the rows. Type the label in column A, the value in column B, and so
on across:

| Cell A (Parameter) | Cell B (Value) | Cell C (Unit) | Cell D (Source / rationale) |
|---|---|---|---|
| Stress hour threshold | 0.95 | percentile | Top 5% of demand within region and season. Sensitivity run at 0.90 and 0.99. |
| Extreme hour threshold | 0.99 | percentile | Tail case |
| Analysis window start | (your pull start) | date | 24 months back from pull, from the manifest |
| Analysis window end | (your pull end) | date | Start of pull month, from the manifest |
| Imbalance tolerance | 5.0 | percent | Above this, an hour is flagged in QA |
| Shortfall cost, low | 40 | USD per MWh | See 8.3 |
| Shortfall cost, central | 100 | USD per MWh | See 8.3 |
| Shortfall cost, high | 200 | USD per MWh | See 8.3 |

So `A3` is "Stress hour threshold", `B3` is `0.95`, and so on down to row 10. For
the two date rows, open `data/raw/_manifest.csv` (double click it, it opens in
Excel) and copy the `window_start` and `window_end` values in.

### Mark the input cells visually

Analysts colour the cells a user is allowed to change, so nobody edits a formula
by accident. Do it here:

1. Click cell `B3`, then hold **Shift** and click `B10`. That selects the whole
   value column, B3 through B10.
2. On the **Home** ribbon, find the **Fill Color** button (a paint bucket icon).
   Click the small arrow next to it and pick a light blue.
3. Click cell `A12` and type this note so the convention is documented:
   `Blue cells are inputs. Everything else is calculated.`

That colour convention is standard in financial modelling, and you already used
the same idea building the NASA parts cost model, so you can speak to it in an
interview.

## 8.3 The cost assumption, sourced

To turn megawatt hours of forecast shortfall into dollars, you need a price per
megawatt hour. **Do not invent this number.** It is the single most attackable
part of the analysis, so it is sourced here for you, with a low, central, and
high value rather than one point estimate.

The key insight, and the thing that makes your handling defensible: a shortfall
happens when actual demand exceeds the forecast, so the missing power is bought in
the **real-time market**, and stress hours (the top 5% of demand, driven by
heatwaves) are exactly when real-time prices spike far above the annual average.
Using an annual-average price is therefore a conservative floor, not the true cost.

The figures below all come from the U.S. Energy Information Administration, which
is the same agency your data comes from, so they are consistent and easy to cite.

- **Low, $40/MWh.** The 2025 U.S. demand-weighted average wholesale power price
  across the eleven regions EIA tracks. This treats a stress-hour megawatt hour
  as if it were an average one, which understates the real cost, hence "low."
  Source: EIA Short-Term Energy Outlook, January 2025.
- **Central, $100/MWh.** Reflects that stress hours coincide with price spikes.
  In summer 2022 EIA reported monthly average on-peak wholesale prices near
  $98/MWh in California's CAISO and above $100/MWh in the Northeast during heat
  events. Source: EIA Today in Energy, summer 2022 wholesale price briefings.
- **High, $200/MWh.** Sustained heatwave stress pricing. EIA reported the ERCOT
  North hub averaging $182/MWh in July 2022 during record demand. This still sits
  well below the extreme scarcity spikes (which have hit $1,000 to $9,000/MWh),
  so it is a defensible upper edge for typical stress hours, not a worst case.
  Source: EIA Today in Energy, "Wholesale U.S. electricity prices were volatile in
  2022."

Enter these three numbers in `B8`, `B9`, `B10` (they are already in the table
above). In your memo, write the cost result as a range and name the source in the
same sentence, like this:

> "Using an EIA-sourced real-time price band of $40 to $200 per MWh, with a $100
> central case reflecting heat-driven stress pricing, PJM's stress-hour shortfall
> corresponds to roughly A to B million dollars over the 24-month window. The
> estimate is linear in the price assumption and should be read as an order of
> magnitude."

That sentence is defensible. "The forecast error cost $47 million" is not.

## 8.4 Tab 2: `BA_Reference`

Click the `BA_Reference` tab. This is a lookup so a reader who does not know what
"SWPP" means can find out. Recreate the eight-row table from Part 4.5:

1. In row 1, type column headers in `A1` through `E1`: `Code`, `Name`, `Region`,
   `Local timezone`, `Peak demand (MW)`.
2. Fill rows 2 through 9 with the eight balancing authorities: PJM, MISO, CISO,
   ERCO, ISNE, NYIS, SWPP, SOCO, with their names, regions, and timezones from the
   Part 4.5 table.
3. The `Peak demand (MW)` column comes from your own output. To get it, open
   `src/scratch.sql`, paste the query below, save, and run `python src\query.py`,
   then copy each number in:

```sql
SELECT ba_code, ROUND(MAX(demand_mw)) AS peak_mw
FROM fact_grid_hourly
GROUP BY ba_code
ORDER BY peak_mw DESC;
```

## 8.5 Tab 3: `Data_Quality`

Click the `Data_Quality` tab. You are importing the data-quality summary your
validation script already wrote.

1. Open `reports/data_quality_summary.csv` (double click, it opens in Excel).
2. Select all of it: click the top-left cell, press **Ctrl+A**, then **Ctrl+C**.
3. Go back to `assumptions.xlsx`, click the `Data_Quality` tab, click cell `A1`,
   and press **Ctrl+V**.

Now add conditional formatting so problem regions jump out:

1. Find the `pct_complete` column. Click its column header letter to select the
   whole column, or select just the data cells in it.
2. **Home** ribbon, **Conditional Formatting**, **Highlight Cells Rules**, **Less
   Than**. Type `99` and choose the red fill option. Click **OK**. Any region
   under 99% complete now shows red.
3. Repeat for the `median_abs_imbalance_pct` column, but use **Greater Than** with
   a value of `1`. Regions whose reporting does not balance cleanly now show red.

This one screenshot is worth a paragraph of text in your methodology page later.

## 8.6 Tab 4: `Sensitivity`

Click the `Sensitivity` tab. This proves your conclusion does not depend on one
lucky assumption. It is a small grid: rows are the stress threshold, columns are
the cost assumption, and each cell is the estimated stress cost for your worst
region.

The honest way to build this is a real Excel **Data Table**, but that requires a
live formula wired to input cells, which is fiddly for a first spreadsheet. Here
is the simpler, equally defensible version that a beginner can finish reliably:

1. In `A1` type `Estimated stress cost ($M), worst region`.
2. In `B2`, `C2`, `D2` type the three cost cases: `$40/MWh`, `$100/MWh`,
   `$200/MWh`.
3. In `A3`, `A4`, `A5` type the three thresholds: `0.90`, `0.95`, `0.99`.
4. For each of the nine inner cells, compute the cost by hand once. You need the
   stress-hour shortfall in MWh at each threshold for your worst region. Get it
   from the warehouse: open `src/scratch.sql`, paste the query below, changing
   `0.95` to each threshold and `'PJM'` to your worst region, run it, and read off
   `stress_shortfall_mwh`:

```sql
SELECT ROUND(SUM(CASE WHEN demand_pctile >= 0.95 THEN shortfall_mw ELSE 0 END)) AS stress_shortfall_mwh
FROM fact_grid_hourly
WHERE ba_code = 'PJM';
```

5. Each cell is then `shortfall_mwh * cost / 1,000,000`. For example, if the 0.95
   shortfall is 300,000 MWh and the cost is $100, the cell is
   `300000 * 100 / 1000000 = 30`, meaning $30M. You can type the multiplication
   straight into the cell as a formula, like `=300000*100/1000000`.

If the nine numbers all tell the same story (your worst region stays worst, the
cost scales smoothly), your conclusion is robust to the assumptions, and saying
so in the memo is a strong close.

> **Save the workbook** (Ctrl+S) and, if you have set up GitHub from Part 2.3,
> commit your progress: in PowerShell run `git add -A`, then
> `git commit -m "Add Excel assumptions register with sourced cost band"`, then
> `git push`.

---

# PART 9: PHASE 5, POWER BI DATA MODEL

**Time budget: 90 minutes.**

Power BI has three main views, and you switch between them with three icons on the
far left edge of the window:

- **Report view** (a bar-chart icon): where you build the visual pages.
- **Table view** (a grid/table icon): where you see the raw rows of a table.
- **Model view** (three connected boxes): where you draw the relationships between
  tables.

Keep that in mind, because the steps below tell you which view to be in. The
horizontal strip of tabs across the very top (Home, Insert, Modeling, View, and so
on) is the **ribbon**, and each tab changes the buttons shown underneath it.

## 9.1 Load the six data files

1. Open **Power BI Desktop**. If a start screen appears, close it, or choose
   **Blank report**.
2. On the **Home** ribbon, click **Get data** (or the dropdown under it), then
   **More...**. A dialog opens.
3. In the search box type `Parquet`, select **Parquet**, and click **Connect**.
4. It asks for a file path or URL. Click **Browse** and go to
   `$HOME\grid-stress-dashboard\data\processed`. Select `dim_ba.parquet` and open
   it. Click **OK**, then in the preview window click **Load**.
5. Repeat steps 2 through 4 for each of the other five files, one at a time:
   `dim_date.parquet`, `dim_fuel.parquet`, `fact_grid_hourly.parquet`,
   `fact_fuel_hourly.parquet`, `analysis_stress_penalty.parquet`.

When you are done, look at the **Data** pane on the right edge. You should see six
tables listed. If you expand one by clicking the arrow next to it, you see its
columns.

> If the Parquet connector errors out (older Power BI builds), open
> `src/04_export_for_bi.py`, uncomment the CSV fallback block at the bottom,
> re-run `python src\04_export_for_bi.py`, and load the `.csv` files from
> `data/processed` instead using **Get data**, **Text/CSV**.

## 9.2 Check the column types

Power BI usually reads parquet types correctly, but confirm the important ones,
because a wrong type breaks filters and time features silently.

1. On the **Home** ribbon, click **Transform data**. The **Power Query Editor**
   opens in a new window. On its left is a **Queries** list with your six tables.
2. Click `fact_grid_hourly`. Each column header has a tiny type icon on its left
   (for example `123` for a whole number, a calendar for a date). Confirm these:

| Column | Should be | Icon to look for |
|---|---|---|
| `date_key` | Date | calendar |
| `ts_utc`, `ts_local` | Date/Time | calendar-clock |
| every column ending `_mw`, `_pct`, `_mwh` | Decimal Number | `1.2` |
| `hour_local` | Whole Number | `123` |
| `is_stress_hour`, `is_extreme_hour` | True/False | two-state toggle |

3. To change a type, click the little icon on the column header and pick the right
   type from the menu. Getting `is_stress_hour` in as **True/False** (not Text)
   matters, because your DAX will compare it against `TRUE`.
4. Check `dim_date` too: `date_key` should be **Date**, and `is_weekend` should be
   **True/False**.
5. When everything looks right, click **Close & Apply** (top left of the Power
   Query window). You return to the main Power BI window.

## 9.3 Draw the relationships

Click the **Model view** icon on the far left (the three connected boxes). You see
your six tables as boxes, possibly with some auto-detected lines between them.

1. First, delete any auto-detected relationship you did not make. Click a
   connecting line to select it (it turns bold), then press **Delete**. Clear them
   all so you start clean.
2. Now create each relationship by **dragging one field onto another**. To make
   the first one: in the `fact_grid_hourly` box, click and hold on the `ba_code`
   field, drag it onto the `ba_code` field in the `dim_ba` box, and release. A line
   appears.
3. Build all four this way:

| Drag this field | Onto this field |
|---|---|
| `fact_grid_hourly[ba_code]` | `dim_ba[ba_code]` |
| `fact_grid_hourly[date_key]` | `dim_date[date_key]` |
| `fact_fuel_hourly[ba_code]` | `dim_ba[ba_code]` |
| `fact_fuel_hourly[fuel_code]` | `dim_fuel[fuel_code]` |

4. Confirm each one is set up right. Double click a relationship line. A dialog
   opens showing **Cardinality** and **Cross-filter direction**. Every one of your
   four should read **Many to one (\*:1)** with the fact table on the "many" side,
   and **Cross-filter direction: Single**. If cardinality shows something else, the
   usual cause is a type mismatch on the key; go back to Power Query and make both
   sides the same type.

**Do not use "Both" for cross-filter direction on any relationship.** Single
direction, fact filtered by dimension, is the correct star-schema wiring and the
first thing a Power BI literate interviewer checks.

## 9.4 Mark the date table

Still useful to do early. In the **Data** pane, click `dim_date` to select it. On
the **Table tools** ribbon that appears, click **Mark as date table**, choose
**Mark as date table**, and in the dialog pick `date_key` as the date column.
Click **OK**. Without this, Power BI's time features can misbehave quietly.

## 9.5 Give the fuel table a date key

`fact_fuel_hourly` has `ts_utc` but no `date_key`, so it cannot join to `dim_date`
on its own. Add a calculated column:

1. In the **Data** pane, right click `fact_fuel_hourly` and choose **New column**.
2. A formula bar appears at the top. Delete whatever is there and type exactly:

```dax
date_key = DATEVALUE ( FORMAT ( 'fact_fuel_hourly'[ts_utc], "YYYY-MM-DD" ) )
```

3. Press Enter. A new `date_key` column appears on the table.
4. Go to **Model view** and drag `fact_fuel_hourly[date_key]` onto
   `dim_date[date_key]` to relate them, Many to one, Single direction, same as
   before.

> Cleaner alternative for later: add this column in `03_build_warehouse.sql`
> instead, so all transformation logic lives in one place. If you do that, skip
> this step and mention the tradeoff in your README. Knowing where logic belongs
> is a senior habit.

## 9.6 Make a home for your measures

Measures are the calculations you will write in Part 10. Keep them all in one tidy
table so the field list stays navigable.

1. **Home** ribbon, **Enter data**. A small table-creation dialog opens.
2. Do not type any data. Just set the table **Name** to `_Measures` (the
   underscore makes it sort to the top) and click **Load**.
3. It creates a table with one empty column. You will delete that column after you
   add your first measure, since a table cannot be totally empty until it has a
   measure in it.

## 9.7 Hide the plumbing

Users of your report should click meaningful fields, never raw keys. In the
**Data** pane, right click each of these and choose **Hide in report view**:

- `ba_code` and `date_key` on both fact tables
- `sort_order` on `dim_fuel`
- `demand_pctile` on `fact_grid_hourly`

The data still works in relationships and measures; it just no longer clutters the
field list.

## 9.8 Build the What If parameter for cost

This is the feature that makes your cost analysis interactive, and it is the single
most impressive thing in the file, because it lets a viewer drag a slider and watch
the dollar estimate move, which visibly demonstrates that the cost is an assumption.

1. **Modeling** ribbon, click **New parameter**, then **Numeric range**.
2. In the dialog, set **Name** to `Cost per MWh`.
3. Set **Minimum** to `40`, **Maximum** to `200`, **Increment** to `10`, and
   **Default** to `100`. These are the low, high, and central values you sourced
   in Part 8.3.
4. Leave **Add slicer to this page** checked, and click **Create**.

Power BI creates a small table called `Cost per MWh` and, inside it, a measure
called `Cost per MWh Value`, plus it drops a slider slicer onto your page. Your
cost measures in Part 10 will multiply by `Cost per MWh Value`, so the slider
drives every dollar figure live.

> **Save now.** Press **Ctrl+S**, navigate to `$HOME\grid-stress-dashboard\powerbi`,
> and save as `grid_stress`. Save often from here on, Power BI does not autosave.

---

# PART 10: PHASE 6, DAX MEASURES

**Time budget: 60 minutes.**

DAX is the formula language Power BI uses for calculations. A **measure** is a
named calculation that recomputes automatically as the user filters and slices.
You will create every measure below in the `_Measures` table you made in Part 9.6.

### How to enter a measure (do this for every one below)

1. In the **Data** pane on the right, click the `_Measures` table once to select
   it. New measures land in whatever table is selected, so this matters.
2. On the **Home** ribbon, click **New measure**. A formula bar appears at the top
   of the window, under the ribbon.
3. Delete any placeholder text and paste one complete measure from below,
   including its name and the `=` sign. For example, paste
   `Total Demand (MWh) = SUM ( fact_grid_hourly[demand_mw] )` in one go.
4. Press **Enter**. The measure appears in the `_Measures` table with a small
   calculator icon.
5. Repeat for each measure. Paste them **one at a time**, each as its own New
   measure. Do not paste a whole block of several measures into one formula bar,
   Power BI expects one measure per definition.

The `-- lines` inside some measures are comments; you can paste them in and Power
BI ignores them, or leave them out. After you add your very first measure, go back
to the `_Measures` table, right click the leftover empty `Column1`, and choose
**Delete** to tidy up.

Do not build calculations by dragging raw number columns onto visuals and letting
Power BI auto-sum them. Explicit measures are reusable, testable, and the thing
that separates a real model from a drag-and-drop exercise.


## 10.1 Base measures

```dax
Total Demand (MWh) = SUM ( fact_grid_hourly[demand_mw] )

Peak Demand (MW) = MAX ( fact_grid_hourly[demand_mw] )

Avg Demand (MW) = AVERAGE ( fact_grid_hourly[demand_mw] )

Hours Analyzed = COUNTROWS ( fact_grid_hourly )
```

## 10.2 Forecast accuracy, the core of the analysis

```dax
MAPE (%) = AVERAGE ( fact_grid_hourly[abs_pct_error] )

MAPE Normal (%) =
CALCULATE (
    [MAPE (%)],
    fact_grid_hourly[is_stress_hour] = FALSE
)

MAPE Stress (%) =
CALCULATE (
    [MAPE (%)],
    fact_grid_hourly[is_stress_hour] = TRUE
)

MAPE Extreme (%) =
CALCULATE (
    [MAPE (%)],
    fact_grid_hourly[is_extreme_hour] = TRUE
)
```

```dax
-- THE HEADLINE MEASURE. Percentage points of extra error during stress hours.
Stress Penalty (pp) = [MAPE Stress (%)] - [MAPE Normal (%)]

-- The ratio version, which is usually the more quotable one.
Stress Multiple =
DIVIDE ( [MAPE Stress (%)], [MAPE Normal (%)] )

-- Signed error. Positive means the forecast runs high on average.
Forecast Bias (%) = AVERAGE ( fact_grid_hourly[pct_error] )

Forecast Bias at Stress (%) =
CALCULATE ( [Forecast Bias (%)], fact_grid_hourly[is_stress_hour] = TRUE )
```

## 10.3 Exposure and cost

```dax
Stress Hours =
CALCULATE (
    COUNTROWS ( fact_grid_hourly ),
    fact_grid_hourly[is_stress_hour] = TRUE
)

-- Shortfall is the expensive direction: actual demand exceeded forecast.
Shortfall (MWh) = SUM ( fact_grid_hourly[shortfall_mw] )

Stress Shortfall (MWh) =
CALCULATE ( [Shortfall (MWh)], fact_grid_hourly[is_stress_hour] = TRUE )
```

```dax
-- Wired to the What If parameter from Part 9.8, so the slider drives it live.
Est. Stress Cost ($) =
[Stress Shortfall (MWh)] * 'Cost per MWh'[Cost per MWh Value]

Est. Stress Cost ($M) =
DIVIDE ( [Est. Stress Cost ($)], 1000000 )
```

```dax
-- Negative interchange was flipped to net_import_mw in SQL, so positive here
-- means the region is pulling power in from neighbors.
Net Import Share (%) =
DIVIDE (
    SUM ( fact_grid_hourly[net_import_mw] ),
    SUM ( fact_grid_hourly[demand_mw] )
) * 100

Net Import Share at Stress (%) =
CALCULATE ( [Net Import Share (%)], fact_grid_hourly[is_stress_hour] = TRUE )
```

## 10.4 Ramp and renewables

```dax
Max 1h Ramp (MW) = MAX ( fact_grid_hourly[ramp_1h_mw] )

Avg VRE Share (%) = AVERAGE ( fact_grid_hourly[vre_share_pct] )

VRE Share at Stress (%) =
CALCULATE ( [Avg VRE Share (%)], fact_grid_hourly[is_stress_hour] = TRUE )

Total Generation (MWh) = SUM ( fact_fuel_hourly[generation_mw] )

Renewable Generation (MWh) =
CALCULATE (
    [Total Generation (MWh)],
    dim_fuel[is_renewable] = TRUE
)

Renewable Share (%) =
DIVIDE ( [Renewable Generation (MWh)], [Total Generation (MWh)] ) * 100

Dispatchable Share (%) =
DIVIDE (
    CALCULATE ( [Total Generation (MWh)], dim_fuel[is_dispatchable] = TRUE ),
    [Total Generation (MWh)]
) * 100
```

## 10.5 Data quality measure (uses an iterator, worth showing off)

```dax
-- AVERAGEX iterates row by row so ABS() can be applied before averaging.
-- AVERAGE() alone would let positive and negative imbalances cancel out and
-- report a misleadingly clean number.
Avg Abs Imbalance (%) =
AVERAGEX ( fact_grid_hourly, ABS ( fact_grid_hourly[imbalance_pct] ) )

Hours Failing Balance Check =
CALCULATE (
    COUNTROWS ( fact_grid_hourly ),
    FILTER ( fact_grid_hourly, ABS ( fact_grid_hourly[imbalance_pct] ) > 5 )
)
```

If an interviewer asks you to explain one measure, pick this one. The reason
`AVERAGE` would be wrong here is a genuinely analytical point, not a syntax point.

## 10.6 Ranking and dynamic labels

```dax
Region Rank by Penalty =
RANKX (
    ALL ( dim_ba[ba_name] ),
    [Stress Penalty (pp)],
    ,
    DESC,
    DENSE
)

-- Dynamic title that reflects whatever the user has sliced to.
Page Title =
VAR SelectedBA = SELECTEDVALUE ( dim_ba[ba_name], "All Regions" )
VAR SelectedSeason = SELECTEDVALUE ( dim_date[season], "All Seasons" )
RETURN
    "Forecast Accuracy Under Stress: " & SelectedBA & " | " & SelectedSeason
```

Put `Page Title` in a Card visual at the top of each page and turn the card
title off. Dynamic titles are a small touch that makes a report feel built rather
than assembled.

## 10.7 Formatting

For each measure, set the format in **Measure tools**:

| Measure pattern | Format |
|---|---|
| `(%)` and `(pp)` measures | Decimal, 2 places, `%` suffix via custom format |
| `(MWh)` and `(MW)` measures | Whole number, thousands separator |
| `($M)` | Currency, 1 decimal |
| `Stress Multiple` | Decimal, 2 places, add `x` suffix |
| Counts | Whole number, thousands separator |

Unformatted measures showing fourteen decimal places is the fastest way to make a
good model look unfinished.

## 10.8 Optional SQL addition: net load ramp

The ramp measure above is on gross demand. Net load ramp, meaning demand after
subtracting wind and solar, is the more operationally meaningful version, since
it is what dispatchable plants actually have to chase. Add this to
`03_build_warehouse.sql` in the net load block if you have time:

```sql
net_load_mw - LAG(net_load_mw) OVER (
    PARTITION BY ba_code ORDER BY ts_utc
) AS net_load_ramp_1h_mw
```

Then add the matching measure:

```dax
Max Net Load Ramp (MW) = MAX ( fact_grid_hourly[net_load_ramp_1h_mw] )
```

CISO should show a dramatically steeper net load ramp than gross demand ramp,
because solar falls off in the early evening exactly as demand climbs. If your
data shows that, you have independently reproduced the duck curve, and that is a
very good sentence to have in your memo.

---

# PART 11: PHASE 7, DASHBOARD PAGES

**Time budget: 2 hours.**

Now you build the visual pages in **Report view** (the bar-chart icon on the far
left). Five pages. Build them in this order, because page 1 is the one people
screenshot and page 5 is the one that gets you hired.

### The three things you do over and over

Every visual on every page is built the same way, so learn this loop once:

1. **Add a visual.** Click an empty area of the page. In the **Visualizations**
   pane (right side, a row of little chart icons), click the icon for the chart
   type you want. An empty visual appears on the canvas. Drag its corner to size
   it, drag its middle to move it.
2. **Give it data.** With the visual selected, its **field wells** show in the
   Visualizations pane (boxes labelled things like X-axis, Y-axis, Values,
   Legend). From the **Data** pane, drag a field or measure into the right well.
   For a bar chart, for instance, drag a category into **Y-axis** and a measure
   into **X-axis**.
3. **Format it.** With the visual selected, click the **Format** icon in the
   Visualizations pane (a paint-roller). This is where you set the title, colours,
   data labels, and so on. The single most important one is the title: click
   **General**, then **Title**, and type a sentence that states a finding.

To add a new page, click the **+** on the page-tab strip at the bottom. Double
click a page tab to rename it.

## 11.1 Global design rules

Apply these across all five pages so the report looks deliberate, not assembled:

- **Font:** Segoe UI everywhere. Do not mix fonts.
- **Colour:** one accent colour for demand, a second for forecast, grey for
  everything contextual. Reserve **red** for stress hours and data-quality flags
  only. If red means three different things it means nothing.
- **Slicers in the same spot on every page.** After you make the BA and Season
  slicers on page 1 (below), you can copy them (Ctrl+C, Ctrl+V) onto each page, and
  use **View**, **Sync slicers** so a selection carries across pages.
- **Titles state findings, not subjects.** "Forecast error rises 40% during peak
  hours" beats "MAPE by stress flag."
- **Leave white space.** Cramming eleven visuals onto a page reads as student
  work no matter how good the analysis is. Four to six visuals per page.

## 11.2 Page 1: Executive Summary

**Goal:** a manager understands the finding in fifteen seconds. Rename this page
`Summary`.

### The slicers (top of the page)

1. Add a visual, choose the **Slicer** icon. Drag `dim_ba[ba_name]` into its
   **Field** well. You now have a clickable list of regions. Position it top right.
2. Add a second **Slicer**, drag `dim_date[season]` into it. Position it under the
   first. These two let a viewer filter the whole page.

### The KPI cards (a row across the top)

A **Card** shows one big number. Make five of them, left to right:

1. Add a visual, choose the **Card** icon (a single large "123"). Drag the measure
   `MAPE Normal (%)` into its **Fields** well. It shows one number.
2. Repeat four more times with `MAPE Stress (%)`, `Stress Penalty (pp)`,
   `Stress Multiple`, and `Est. Stress Cost ($M)`.
3. For each card, use **Format**, **General**, **Title** to label it (for example
   "Error, stress hours"), since the raw measure name is not self-explanatory.

### The main bar chart (middle)

1. Add a visual, choose **Clustered bar chart**.
2. Drag `dim_ba[ba_name]` into **Y-axis** and the measure `Stress Penalty (pp)`
   into **X-axis**.
3. In **Format**, turn on data labels, and sort the bars: click the "..." menu on
   the visual, **Sort axis**, by `Stress Penalty (pp)`, descending.
4. Title it with your actual finding once you can read it, for example "PJM and
   NYIS lose the most forecast accuracy under stress."

### The scatter plot (bottom)

This one does real analytical work: it shows whether regions that import heavily at
peak also forecast worse at peak.

1. Add a visual, choose **Scatter chart**.
2. Drag `Net Import Share at Stress (%)` into **X-axis**,
   `Stress Penalty (pp)` into **Y-axis**, `Peak Demand (MW)` into **Size**, and
   `dim_ba[ba_name]` into **Values** (this labels each bubble).
3. If the bubbles that sit high and to the right are the same regions, you have
   found an interaction, not just a list, and that is what makes an analysis feel
   like insight. Say so in a text box beside it (Insert, Text box).

## 11.3 Page 2: Forecast Accuracy Anatomy

**Goal:** show where in the day and year the error lives. New page, named
`Anatomy`. Four visuals:

| Visual type | Fields to drag |
|---|---|
| **Line chart** | X-axis `hour_local`; drag both `MAPE Stress (%)` and `MAPE Normal (%)` into Y-axis so you get two lines |
| **Column chart** | X-axis `dim_date[year_month]`; Y-axis `MAPE (%)` |
| **Column chart (histogram)** | X-axis `pct_error`; Y-axis `Hours Analyzed`. In Format, set the X-axis binning to about 1 (a 1-percentage-point bucket) |
| **Column chart** | X-axis `dim_ba[ba_name]`; Y-axis `Forecast Bias (%)` |

The histogram matters: if it centres slightly above zero, forecasters are
systematically conservative (biasing high), which is a rational hedge worth stating
out loud. Symmetric means the error is noise, not bias, which implies a different
fix.

## 11.4 Page 3: Stress Hour Deep Dive

**Goal:** show one real event in detail, because abstractions do not persuade. New
page, named `Deep Dive`.

1. First find your worst event. Open `src/scratch.sql`, paste this, save, and run
   `python src\query.py`:

```sql
SELECT ba_code, ts_local, demand_mw, forecast_mw,
       abs_pct_error, net_import_mw, ramp_1h_mw
FROM fact_grid_hourly
WHERE is_extreme_hour
ORDER BY abs_pct_error DESC
LIMIT 20;
```

2. Note the region and date of the top row. Build the page focused on the seven
   days around that date. Use a **date slicer** (add a Slicer, drag
   `dim_date[date_key]` in, and in Format set its style to **Between**) to zoom the
   whole page to that week.

| Visual | Fields |
|---|---|
| **Line chart: demand vs forecast** | X-axis `ts_local`; Y-axis `demand_mw` and `forecast_mw` as two lines |
| **Area chart: the error** | X-axis `ts_local`; Y-axis `forecast_error_mw` |
| **Stacked area: fuel mix** | X-axis `ts_local`; Y-axis `generation_mw`; Legend `dim_fuel[fuel_name]` |
| **Line: net imports** | X-axis `ts_local`; Y-axis `net_import_mw` |
| **Text box** | Type the date, region, peak demand, peak error, and one sentence on what the weather actually was that week |

Look up the real weather for that week (a quick search for "heat wave [region]
[month year]") and put one sentence in the text box. It costs four minutes and
makes the whole project feel like it is about the real world, not a CSV.

## 11.5 Page 4: Fuel Mix and Ramp

New page, named `Fuel & Ramp`.

| Visual | Fields |
|---|---|
| **100% stacked column** | Two columns, stress vs normal, of generation share by `dim_fuel[fuel_group]`. Simplest version: a stacked column with `dim_fuel[fuel_group]` on Legend and `Total Generation (MWh)` on Y, filtered once to stress and once to normal using two copies |
| **Column** | X-axis `dim_ba[ba_name]`; Y-axis `Renewable Share (%)` |
| **Line, filtered to CISO** | X-axis `hour_local`; Y-axis average `demand_mw` and average `net_load_mw` as two lines. Use a visual-level filter to set `ba_name` = California ISO |
| **Column** | X-axis `dim_ba[ba_name]`; Y-axis `Max 1h Ramp (MW)` |

The CISO line chart is the duck curve: net load dips midday when solar floods in,
then ramps hard in the early evening as the sun sets and demand climbs. Title that
visual "The duck curve: CISO net load vs demand."

## 11.6 Page 5: Methodology and Data Quality

**This is the page that separates you from every other applicant.** Almost nobody
builds it. It is mostly text boxes (Insert, Text box) and one table visual.

Put these on the page:

1. A text box with **the question**, verbatim from Part 0.2.
2. A text box with **the stress-hour definition** and its three justifications from
   Part 4.7.
3. A **Table** visual (the grid icon): drag `dim_ba[ba_name]`,
   `Avg Abs Imbalance (%)`, and `Hours Failing Balance Check` into its Columns.
   This is your balance-identity evidence.
4. A **Table** visual with the completeness numbers, or paste a screenshot of your
   Excel `Data_Quality` tab.
5. A text box with the **three handling decisions** from the validation script, in
   plain language.
6. A text box with **limitations**: MISO and SWPP span multiple time zones and use
   one assigned zone; raw rather than adjusted EIA series were used; the cost figure
   is a sourced assumption, not a measurement; 24 months is a short window for
   weather-driven conclusions.
7. A text box with **source and refresh date**, from your pull manifest.

> When you walk an interviewer through the file, go to page 1 first, then jump
> straight to this page. Volunteering your own limitations before anyone asks is
> the single most credibility-building move in a portfolio review.

> **Save** (Ctrl+S). If you set up GitHub, note that the `.pbix` is a large binary
> file. It is fine to commit it, but do not commit the raw data. Run `git add -A`,
> then `git status` to confirm no `data/raw` files are staged, then
> `git commit -m "Add Power BI dashboard, five pages"` and `git push`.

---

# PART 12: PHASE 8, THE ANALYST MEMO

**Time budget: 90 minutes. Do this in a second sitting, not at hour ten.**

## 12.1 Why the memo is the most valuable deliverable

Most student portfolios end at the dashboard. A dashboard shows what happened. A
memo says what to do about it. Analysis that never becomes a decision is not
analyst work, and hiring managers know the difference.

You also happen to be good at this already. You write and edit draft reports at
INFORUM. Use that.

## 12.2 Hard constraint: one page

One page. Not two. If it does not fit, your finding is not sharp enough yet.

## 12.3 Structure

```
GRID FORECAST ACCURACY UNDER STRESS
Eight U.S. balancing authorities, [month year] to [month year]
Jose Aleman | [date]

QUESTION
    One sentence. The question from Part 0.2.

METHOD
    Three or four sentences. Source, window, grain, stress definition.
    Name the row count. Name the tools.

FINDINGS
    1. [The headline. A number, a comparison, a region.]
    2. [The interaction. Something that only shows up when two things
       are looked at together.]
    3. [The surprise, or the honest null result.]

RECOMMENDATION
    One paragraph. Where should effort go first, and why that place
    rather than another. Tie it to a number from the findings.

LIMITATIONS
    Four bullets. The ones from dashboard page 5.

SOURCE
    U.S. Energy Information Administration, Form EIA-930, API v2.
    Data pulled [date]. Code: [github url]
```

## 12.4 Rules for the writing itself

Your project instructions already contain a good list of phrases to avoid. Apply
it here, because a memo full of "leveraged" and "robust framework" undoes the
credibility the analysis earned.

Specifically:

- **Lead every finding with the number.** "PJM's forecast error is 1.6 times
  higher during stress hours" beats "analysis reveals notable variation."
- **Name the region.** Findings about "certain regions" are not findings.
- **Do not hedge the recommendation.** You are allowed to be wrong. You are not
  allowed to be vague. "Prioritize X" is a recommendation. "Consider exploring
  opportunities around X" is not.
- **Write the limitations plainly.** Not "some caveats apply" but "MISO spans
  three time zones and I assigned it one."
- **No summary paragraph at the end.** The findings are the summary.

## 12.5 The recommendation, worked example

Weak:

> The analysis suggests that forecast accuracy could be improved in several
> regions, and stakeholders may wish to consider targeted investments.

Strong:

> Forecasting effort should go to [region] first. It carries the largest stress
> penalty in the set at [N] percentage points, and it is also the most
> import dependent at peak, at [M] percent of demand, so its errors have to be
> covered by neighbors rather than by local reserve. [Other region] has a
> similar penalty but imports almost nothing at peak, so the same error there is
> cheaper to absorb. The ranking changes if the cost assumption falls below
> [X] dollars per MWh, which is why the dashboard exposes that input directly.

The second one names regions, uses two numbers, explains why one region ranks
above another with a similar score, and states the condition under which the
conclusion would flip. That last move is what a good analyst does.

## 12.6 Export

Write it in Word, export to PDF, save as `reports/memo.pdf`. Link it from the
top of your README.

---

# PART 13: FINISHING THE GITHUB REPOSITORY AND README

**Time budget: 45 minutes.**

Your repository has existed since Part 2.3 and you have been pushing to it after
each session. This part is about making it presentable: writing the README that
recruiters actually read, adding screenshots, cleaning up `requirements.txt`, and
confirming your commit history tells a good story. If you skipped the GitHub
setup earlier, go back and do Part 2.3 now, because everything here assumes the
repo already exists.

## 13.1 The README is the product

More people will read your README than will ever open your .pbix file. Treat it
as the deliverable.

## 13.2 Template

Create it the same way as the script files, then paste the template into the
editor tab and fill in the bracketed placeholders:

```powershell
code README.md
```

```markdown
# Grid Stress Dashboard

**Does the U.S. power grid forecast worst exactly when accuracy matters most?**

Analysis of 1.7M hourly records across eight U.S. balancing authorities,
testing whether day ahead demand forecast error concentrates in high stress hours.

![Dashboard](docs/screenshots/executive_summary.png)

## Headline finding

[One sentence with a number. Replace this.]

[Read the one page memo](reports/memo.pdf)

## Question

When the grid is under the most stress, does the day ahead demand forecast get
worse exactly when accuracy matters most, and which regions are most exposed?

## Data

| | |
|---|---|
| Source | U.S. EIA, Form EIA-930, API v2 |
| Regions | PJM, MISO, CISO, ERCO, ISNE, NYIS, SWPP, SOCO |
| Window | 24 months ending [month year] |
| Grain | Balancing authority x hour |
| Volume | ~560K region rows, ~1.1M fuel rows |

## Method

1. **Pull** (`src/01_pull.py`) Paginated extraction from the EIA API with
   retry and backoff. Writes raw parquet plus a provenance manifest.
2. **Validate** (`src/02_validate.py`) Completeness, duplicates, impossible
   values, robust outlier detection, and an EIA-930 balance identity check
   (net generation minus interchange must equal demand).
3. **Model** (`src/03_build_warehouse.sql`) DuckDB star schema. Stress hours
   defined by demand percentile within region and season using window functions.
4. **Visualize** (`powerbi/grid_stress.pbix`) Star schema model, explicit DAX
   measures, What If parameter for cost sensitivity.

## Stress hour definition

An hour in the top 5% of demand for that balancing authority within that season.
Percentile within region makes differently sized grids comparable; within season
prevents the measure from collapsing into a summer versus winter comparison.

## Reproduce

```powershell
git clone [url]
cd grid-stress-dashboard
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Set-Content -Path .env -Value "EIA_API_KEY=your_key"
python src\01_pull.py           # ~10 min
python src\02_validate.py
python src\04_export_for_bi.py
```

Requires Windows 10 or 11, Python 3.10+, and Power BI Desktop.

## Limitations

- MISO and SWPP span multiple time zones; each is assigned one local zone.
- Raw EIA series used rather than adjusted series, keeping provenance simple
  and reporting error visible.
- The cost per MWh figure is a sourced assumption with a sensitivity range,
  not a measurement.
- A 24 month window is short for weather driven conclusions.

## Data quality

See [reports/data_quality_report.md](reports/data_quality_report.md).

## Stack

Python (pandas, requests, pyarrow); SQL (DuckDB); Power BI; Excel
```

## 13.3 Screenshots

Export each dashboard page: **File**, **Export**, **Export to PDF**, then crop
to PNG. Or use the Windows Snipping Tool. Put them in `docs/screenshots/` and
embed the executive summary in the README. A repo with no image gets far less
attention than one with a picture at the top.

## 13.4 requirements.txt

```powershell
pip freeze | Out-File -FilePath requirements.txt -Encoding utf8
```

Use `Out-File -Encoding utf8` rather than `>`. PowerShell's default redirect
writes UTF-16 with a byte order mark, which `pip install -r` chokes on.

Then open it and trim to the packages you actually import. A 200 line freeze file
looks careless.

## 13.5 Commit hygiene

You have been committing as you go since Part 2.3, so by now you have a history.
The point is that it reads as a build log, not one commit called "final." Each
commit is the three-command loop from Part 2.4, with a message describing what
that chunk of work did:

```powershell
git add -A
git commit -m "Add star schema build with stress hour window functions"
git push
```

Good messages, roughly one per phase, look like:

```
Initial project structure with gitignore
Add EIA API pull with pagination and retry
Add data quality validation including EIA-930 balance check
Build star schema with stress hour window functions
Add Power BI model, DAX measures, and dashboard screenshots
Add analyst memo and finished README
```

Someone will look at your commit history. Make it tell a story about how you work.

## 13.6 Final push and make it public

When everything is in, do a last commit and push so the finished README,
screenshots, and memo are all on GitHub:

```powershell
git add -A
git commit -m "Add analyst memo and finished README"
git push
```

If you built the repo private, make it public now so it can go on your resume and
portfolio:

```powershell
gh repo edit --visibility public
```

Then open your repository URL in a logged-out browser (or a private window) to
confirm a stranger can actually see it, the screenshots render, and the memo link
works. A repo that 404s for everyone but you is the last trap to check for.

---

# PART 14: RESUME BULLETS AND INTERVIEW PREP

## 14.1 Where this goes on the resume

Add a `PROJECTS` section between `SKILLS & TOOLS` and `HONORS`. Keep the same
formatting as the rest of the document: bold left, right tab for the date, the
same bullet glyph.

## 14.2 Two bullet options

**Option A, one bullet, if space is tight:**

> Built an end to end analytics pipeline (Python, SQL, Power BI) over 1.7M hourly
> EIA-930 records across 8 U.S. balancing authorities; found day ahead demand
> forecast error was [N]x higher during top 5% demand hours, & ranked regions by
> exposure in a one page recommendation memo.

**Option B, three bullets, if you want the section to carry weight:**

> - Pulled & validated 1.7M hourly grid records from the EIA API in Python
>   (pandas, requests) with paginated retry logic; flagged reporting errors via
>   the EIA-930 balance identity (net generation minus interchange = demand).
> - Modeled a DuckDB star schema using window functions to classify stress hours
>   by demand percentile within region & season, enabling comparison across
>   grids of different size.
> - Built a Power BI dashboard with explicit DAX measures & a What If cost
>   parameter; delivered a one page memo ranking regions by forecast exposure.

Update your skills line to add SQL and DuckDB once the repo is public. Only then.

## 14.3 Questions you will be asked, and the answers

**"Why did you pick this dataset?"**
Do not say "it was available." Say you wanted a question where the answer had an
operational consequence, and forecast error during grid stress is one where being
wrong costs money in a traceable way. Mention that PJM covers Maryland, so one of
the eight regions is the grid you live on.

**"Why not just use Excel?"**
1.7 million rows across two fact tables. Then add that the stress definition
requires percentile ranking partitioned by region and season, which is a window
function, and that expressing it in SQL is clearer than any Excel equivalent.

**"How did you define a stress hour, and why that way?"**
Give all three justifications from Part 4.7. This question is really testing
whether your threshold was arbitrary. It was not, and you can prove it, and you
ran sensitivity on it.

**"How do you know your data is right?"**
The balance identity. Walk them through it: net generation minus interchange must
equal demand as a matter of physics, you measured the residual per region, and
you reported it rather than silently correcting it. This is your strongest
answer in the whole interview. Lead with it if you get any opening.

**"What would you do differently with more time?"**
Have three ready. Suggestions: join weather data to test whether error tracks
temperature forecast error rather than demand level; extend to five years to
separate weather variance from trend; use EIA's adjusted series and compare
results against the raw series to quantify how much the choice matters.

**"What surprised you?"**
Have a real answer. It might be a region you expected to look bad that did not,
or the size of the imbalance in one BA's reporting, or the shape of the bias
distribution. If nothing surprised you, you did not look hard enough at your own
output.

**"Walk me through your dashboard."**
Sixty seconds on page 1, then go straight to page 5, methodology. Then let them
drive. Do not narrate every visual.

## 14.4 What not to claim

Do not say you "built a forecasting model." You did not. You evaluated somebody
else's forecasts, which is a different and arguably more useful thing. Overclaim
once and everything else you said becomes suspect.

---

# PART 15: TROUBLESHOOTING

**Windows environment issues**

| Symptom | Likely cause | Fix |
|---|---|---|
| `cd` fails with "Cannot find path... because it does not exist" | Typed a placeholder path literally instead of the real one | This guide no longer has this problem: use `Set-Location "$HOME\grid-stress-dashboard"` exactly as written. If you still get this, the project was never created there; run `Get-ChildItem -Path $HOME -Recurse -Directory -Filter "grid-stress-dashboard" -ErrorAction SilentlyContinue` to find it. |
| `python` not recognized | PATH not refreshed, or App Execution Alias | Close and reopen PowerShell. If it opens the Microsoft Store, disable the python.exe alias in Settings, Apps, Advanced app settings, App execution aliases. |
| `code` not recognized | VS Code PATH not refreshed after install | Close and reopen PowerShell. If it still fails, open VS Code manually, press `Ctrl+Shift+P`, run "Shell Command: Install 'code' command in PATH", then reopen PowerShell. |
| `Activate.ps1 cannot be loaded` | PowerShell execution policy | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Scripts run but packages missing | Virtual environment not activated in this window | Look for `(.venv)` in your prompt. Run `.venv\Scripts\Activate.ps1` again. |
| `.env` not found by dotenv | File is actually `.env.txt`, or UTF-16 encoded | `Get-ChildItem -Force` to see the real name. Recreate with `Set-Content -Encoding ascii`. |
| `pip install -r requirements.txt` fails on line 1 | requirements.txt is UTF-16 from `>` redirect | Regenerate with `pip freeze \| Out-File -Encoding utf8 requirements.txt` |
| `data\raw` folder empty after pull | Ran the script from the wrong directory | `Get-Location` to check. Run from the project root, not from inside `src`. |
| Git shows the whole data folder as changes | `.gitignore` saved as `.gitignore.txt` | `Get-ChildItem -Force`, rename, then `git rm -r --cached data` |
| Long path errors on parquet writes | `$HOME` itself resolves to a deeply nested path, common with OneDrive-redirected profiles | Check with `Get-Location`. If it is unusually long, use `C:\dev\grid-stress-dashboard` instead and repeat Part 1.2 from that location. |
| `gh` not recognized | GitHub CLI PATH not refreshed after install | Close and reopen PowerShell. Confirm with `gh --version`. |
| `git push` asks for a username and password | Not logged in via the CLI | Run `gh auth login` (Part 2.3). GitHub no longer accepts your account password on the command line. |
| `Author identity unknown` on first commit | Git identity not set | Run the two `git config --global` commands in Part 2.3 step 2, then commit again. |
| `git status` shows files inside `data/` or `.env` | `.gitignore` not found or misnamed | `Get-ChildItem -Force` to confirm it is exactly `.gitignore`. If you already committed data, run `git rm -r --cached data` and commit again. |
| `gh repo create` says the name already exists | You already created it, or a name clash | Skip creation. Link the existing repo with `git remote add origin <url>` then `git push -u origin main`. |

**Data and modeling issues**

| Symptom | Likely cause | Fix |
|---|---|---|
| HTTP 403 on every call | Key wrong, or quotes/spaces in `.env` | Open `.env`, confirm `EIA_API_KEY=abc123` with no quotes and no trailing space |
| HTTP 404 | Route string typo | Compare against Part 4.2 character by character. Trailing slash on `/data/` is required. |
| HTTP 429 repeatedly | Requesting too fast | Raise `POLITE_DELAY` to 1.0 |
| Row count mismatch warning | Pagination drift | Confirm `sort[0][column]=period` is present. Unsorted pagination is unstable. |
| Zero rows returned | Date window is in the future, or BA code wrong | EIA lags by a day or two. Check `START` and `END` printed at script launch. |
| `strptime` error in DuckDB | Period format differs from `%Y-%m-%dT%H` | Print a few raw `period` values and adjust the format string |
| All `imbalance_mw` are null | A type code is missing for that BA | Check the pivot in `stg_region`. Some smaller BAs do not report all four types. |
| Power BI cannot read parquet | Older Power BI Desktop | Update via Microsoft Store, or uncomment the CSV fallback block at the bottom of `04_export_for_bi.py` and load CSVs |
| DAX stress measures return blank | `is_stress_hour` imported as text | Change the column type to True/False in Power Query, then refresh |
| Relationship will not create | Type mismatch on the key | Both `date_key` columns must be Date, both `ba_code` columns must be Text |
| Peak demand appears at 3am local | Timezone converted the wrong way | See Part 7.7. Run the verification query. |
| Numbers differ from the EIA website | Raw vs adjusted series, or a timezone difference | Expected. Document it. This is a limitation, not a bug. |
| Duck curve does not appear for CISO | Solar aggregated into 'OTH' for some periods | Check `fact_fuel_hourly` for which fuel codes CISO actually reports |

---

# APPENDIX A: BALANCING AUTHORITY REFERENCE

| Code | Full name | Region | Typical peak season |
|---|---|---|---|
| PJM | PJM Interconnection, LLC | Mid Atlantic incl. Maryland | Summer |
| MISO | Midcontinent Independent System Operator | Midwest / South | Summer |
| CISO | California Independent System Operator | California | Summer |
| ERCO | Electric Reliability Council of Texas | Texas | Summer |
| ISNE | ISO New England | New England | Summer, with winter gas constraint |
| NYIS | New York Independent System Operator | New York | Summer |
| SWPP | Southwest Power Pool | Central plains | Summer |
| SOCO | Southern Company Services | Southeast | Summer |

There are roughly 66 balancing authorities covering the contiguous 48 states.
If you want to extend the project later, `US48` is the aggregate code for the
whole lower 48.

# APPENDIX B: FUEL TYPE CODES

| Code | Fuel | Dispatchable | Renewable |
|---|---|---|---|
| COL | Coal | Yes | No |
| NG | Natural gas | Yes | No |
| NUC | Nuclear | No (baseload) | No |
| OIL | Petroleum | Yes | No |
| WAT | Hydro | Yes | Yes |
| SUN | Solar | No | Yes |
| WND | Wind | No | Yes |
| OTH | Other | Varies | Varies |
| UNK | Unknown | Unknown | Unknown |

Note the collision: `NG` is the fuel code for natural gas in the fuel type
dataset, and also the type code for net generation in the region dataset. They
are different fields in different tables. Keep them straight or you will spend
an hour confused.

# APPENDIX C: GLOSSARY

| Term | Definition |
|---|---|
| Balancing authority | The entity responsible for keeping generation and load matched in real time within its footprint |
| Demand (D) | Actual electricity consumed, in megawatthours |
| Day ahead forecast (DF) | The demand the operator predicted the day before |
| Net generation (NG) | Electricity produced within the footprint, net of plant use |
| Total interchange (TI) | Net power flow to neighbors. Positive means exporting. |
| Net load | Demand minus wind and solar. What dispatchable plants must supply. |
| Ramp | Change in demand or net load from one hour to the next |
| Duck curve | The net load shape created when solar output falls in the early evening as demand rises |
| MAPE | Mean absolute percentage error |
| Stress hour | Defined here as the top 5% of demand hours within a region and season |
| Star schema | A data model with one central fact table joined to descriptive dimension tables |
| Grain | The precise meaning of one row in a fact table |

# APPENDIX D: BUILD CHECKLIST

Print this. Tick as you go.

**Setup**
- [ ] Python environment created and packages installed
- [ ] Folder structure created
- [ ] `.gitignore` written BEFORE first commit
- [ ] Git initialized, identity set, logged in with `gh auth login`
- [ ] GitHub repo created and first commit pushed (Part 2.3)
- [ ] EIA API key obtained and stored in `.env`
- [ ] Smoke test returns HTTP 200 and five rows
- [ ] Pushing after each work session with `git add -A; git commit; git push`

**Data**
- [ ] `01_pull.py` completes, ~1.7M rows, 16 parquet files plus manifest
- [ ] `02_validate.py` completes and the report has been read, not skimmed
- [ ] `query.py` created and used to run at least one spot-check query
- [ ] Worst region for missing hours identified
- [ ] Worst region for balance imbalance identified

**Model**
- [ ] `03_build_warehouse.sql` runs without error
- [ ] `04_export_for_bi.py` prints the headline stress penalty table
- [ ] Headline result written down somewhere before dashboard work begins

**Excel**
- [ ] Assumptions tab with input cells color coded
- [ ] Cost per MWh sourced with a citation, low/central/high entered
- [ ] Data quality tab with conditional formatting
- [ ] Sensitivity table built

**Power BI**
- [ ] Six tables loaded, data types correct
- [ ] Four relationships, all single direction, fact to dimension
- [ ] `dim_date` marked as date table
- [ ] `_Measures` table created and sorted to top
- [ ] Foreign keys hidden
- [ ] What If cost parameter created with slicer
- [ ] All measures from Part 10 created and formatted
- [ ] Five pages built
- [ ] Slicers synced across pages
- [ ] Every visual title states a finding, not a subject

**Delivery**
- [ ] Memo written, one page, exported to PDF
- [ ] README complete with a screenshot at the top
- [ ] `requirements.txt` trimmed
- [ ] Commit history reads as a build log
- [ ] Final commit pushed; repo set to public (Part 13.6)
- [ ] Repo opens for a logged-out visitor, images and memo link work
- [ ] Resume `PROJECTS` section added
- [ ] SQL added to skills line
- [ ] Portfolio site updated with a link

---

**End of guide.**

Source note: all data comes from the U.S. Energy Information Administration,
Form EIA-930, retrieved through EIA API v2. The API is free and requires only a
registered key. Data availability, route names, and facet codes should be
verified against the current EIA documentation at the time you build, since
federal data products do change.