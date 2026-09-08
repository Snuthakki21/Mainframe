# Start here — one Markdown file per process, one kickoff

## 1. Put the framework beside your existing source repository

On your work Windows machine, copy the whole `mainframe_migration` folder beside
your existing source folder, under the same parent. For example:

| Folder or file | What belongs there |
|---|---|
| `C:\work\mainframe_migration\` | This framework, including `modernize.py`, `target.json`, the migration skill, tests and sample. |
| `C:\work\mainframe-source\` | Your existing local JCL, programs, copybooks, control members and DDL. |
| `C:\work\process-inputs\PAYMENTS.md` | The saved Markdown for one complete process. |
| `C:\work\test-evidence\` | Available matched mainframe input/output and run evidence. |
| `C:\work\migration-results\` | The output destination used in the kickoff below. |

The source folder does not have to be named `mainframe-source`; use its actual name
in the kickoff. It may already be a Git checkout, but Git is not a prerequisite for
running the framework. The local runner never clones, pulls, commits, creates
branches, or pushes. Open `C:\work\mainframe_migration` in VS Code; the agent reads
the source through the supplied local path. Your existing approved Copilot setup
is used, and the Python runner needs no separate model API key.

Place these folders on the work machine before initializing a real process. The
shipped sample uses relative paths and can move with the framework folder. `init`
saves absolute local paths for a real process; if you relocate the folders later,
update the affected configuration paths or initialize a new configuration at its
new location. Copying an already initialized configuration from another computer
does not automatically remap that computer's paths.

## 2. Start in the framework folder and verify it

Open a PowerShell terminal on the work machine. Run these commands before changing
`target.json`:

```powershell
Set-Location 'C:\work\mainframe_migration'
python --version
python modernize.py doctor
.\VERIFY-WINDOWS.cmd
```

Use an approved Python **3.10 or later**. Python includes the SQLite support needed
for the default target. No `pip install`, `npm install`, Java SDK or .NET SDK is
needed to start with Python and SQLite. If the machine uses the Windows Python
launcher instead of a `python` command, use `py -3 --version` and
`py -3 modernize.py doctor`; use `py -3` in place of `python` in subsequent commands.
`VERIFY-WINDOWS.cmd` checks both launch methods. If neither is available, request
the approved Python installation through your usual work-machine process.

`doctor` prints the Python, operating system and SQLite details. The verifier
checks the shipped file hashes, runs both regression suites, and
exercises all nine selections on a disposable copy of the sample. It records
missing SDKs/drivers separately; it never presents a skipped .NET or remote test
as passed. It does not change your central target choice or install packages.
Read the `evidence/package-check/.../verification.json` location printed at the end.

The expected verifier outcome is `CHECKS_PASSED_WITH_EXPLICIT_RUNTIME_GAPS` when
the available checks pass. Read the per-target statuses: a missing Java/.NET SDK
or database driver remains an explicit gap. A `FAILED` receipt names the failing
check and its log; it is not a successful setup check. The package's previous
development evidence is from Linux, so run this verifier on the actual work machine.

To see the default synthetic process run directly from the same folder:

```powershell
python modernize.py demo
Start-Process '.\output\synthetic_accounts\modernization_report.html'
```

This reads `sample/process.md`, discovers five jobs and six steps in the supplied
sample source, generates Python, executes the supplied scenarios against local
SQLite and compares their expected files, return codes and database state. Its
successful status is `SYNTHETIC_TARGET_VALIDATED`. This exercises the framework
with synthetic evidence; it does not validate PAYMENTS or any other real process.

## 3. Choose the target in one place

`target.json` already selects **Python + SQLite**. Leave those values in place for
the first run. When you want a different target, change only the existing
`language` and `database` values:

| Desired result | language | database |
|---|---|---|
| Local Python test | python | sqlite |
| Python with Oracle | python | oracle |
| Python with BigQuery | python | bigquery |
| C# with SQLite | dotnet | sqlite |
| C# with Oracle | dotnet | oracle |
| C# with BigQuery | dotnet | bigquery |
| Java with SQLite | java | sqlite |
| Java with Oracle | java | oracle |
| Java with BigQuery | java | bigquery |

Keep the remaining JSON entries. `versions` selects the approved JDK release and
.NET framework; it does not install them. `dependencies` declares exact driver
versions. `connections` stores environment-variable names, never credentials.
There is no separate per-job target switch. A process can point to a central file
with `target_file`; otherwise the package-root target.json is used.

## 4. Start a real migration with one agent request

Save the process documentation as a UTF-8 `.md` file. If you use Team Composer to
convert an existing spreadsheet, do that once outside the framework. The saved
file is the input for subsequent runs. Job headings and step tables like those
in **docs/MARKDOWN_INPUT.md** are accepted, including separate processing sections
with Input/Output columns or a Description column.

Paste the following in VS Code Copilot Agent mode or Devin. Replace the process
name and paths with your local values. There is no custom slash command dependency.

```text
Read AGENTS.md and .agents/skills/migrate-process/SKILL.md.
Migrate process PAYMENTS using the local repository C:\work\mainframe-source
and Markdown process file C:\work\process-inputs\PAYMENTS.md.
Read language and database ONLY from target.json.
Create or reuse processes/PAYMENTS/process.json.
Use C:\work\migration-results as the output root.
Discover dependencies from the source. Use the same source behavior, including
unusual exceptions; do not fix business rules or repair failed candidates.
Use any available baseline evidence under C:\work\test-evidence.
Derive dataset bindings and destinations from source-backed information; ask
about missing layouts, paths and scheduler evidence in the consolidated report.
Drive discovery, source analysis, selected-target generation/registration,
local execution, comparisons, read-only adversarial review, and reporting.
Reuse intact, source-linked prior work. Do not inherit validation from another
target. Do not perform Git operations or change expected outputs.
Put status and the remaining plain-English SME questions in the single report.
```

The tool exposes a request when agent generation is needed. The SAME agent session
reads that request, creates a candidate, records its review, registers it, and
runs validation. This is not a promise that a bare Python command can invoke your
IDE assistant. No live Copilot or Devin session was executed in this delivery.

The Markdown identifies the process scope; it does not replace JCL, program code,
copybooks, DDL, file layouts or matched test evidence. A Description-only table is
valid documentation, but cannot supply missing dataset names or business logic.
Missing evidence remains visible in the report while discovery gathers what it can.
You can omit the evidence directory from the kickoff when evidence is not available.

For reference, the agent can initialize a process with this command. It writes
the configuration and immediately performs discovery; missing evidence can produce
a `BLOCKED` report even though configuration creation succeeded:

```powershell
python modernize.py init --process PAYMENTS --repository "C:\work\mainframe-source" --inventory "C:\work\process-inputs\PAYMENTS.md" --config "processes/PAYMENTS/process.json" --output "C:\work\migration-results"
```

No `--sheet` is needed for Markdown. An existing configuration is reused with
`run`, not overwritten by `init`. The agent fills in source-backed bindings and
evidence in that configuration as discovery proceeds.

For a first real process, expect the following sequence:

| Stage | What you should see |
|---|---|
| Markdown intake | Jobs, step tables, sections and documented datasets in `process_flow.json`. |
| Source discovery | JCL/program/copybook/schema references and unresolved dependencies in the report. |
| Initial configuration | Local paths, empty evidence/binding fields where facts are not yet established, and questions for the missing information. |
| Agent generation | A complete selected-target candidate only after the required source and execution facts are resolved. |
| Local validation | Actual native execution and comparisons only for supplied runnable cases; missing evidence is labeled. |

An initial `BLOCKED` status is expected when source, dataset layouts, scheduler
order or baseline evidence is missing. The agent should resolve what it can from
your repository, consolidate the remaining questions, and continue when the needed
evidence is supplied. A parsed `.md` alone cannot establish executable business
logic or expected results.

## 5. Change architecture later

Edit the two values in target.json and give the same agent kickoff, referring to
the existing process configuration. For already generated supported source models,
the local command can emit the new target directly:

```powershell
python modernize.py run --config "processes/PAYMENTS/process.json"
```

A DB-only change keeps eligible language files. A language change keeps eligible
source models and emits native code. The framework always creates a separate
selected-target artifact and fresh evidence. Failed sealed attempts remain intact.

## 6. Read one process report

With the default output root, the current report is:

```text
output/PAYMENTS/modernization_report.html
```

With the kickoff's output root, it is
`C:\work\migration-results\PAYMENTS\modernization_report.html`.

Under the chosen output root, use these destinations:

| Result | Path relative to the output root |
|---|---|
| Current consolidated report | `PAYMENTS/modernization_report.html` |
| Current machine-readable status | `PAYMENTS/latest_result.json` |
| Parsed process flow and dataset destinations | `PAYMENTS/runs/<run-id>/process_flow.json` |
| Source discovery | `PAYMENTS/runs/<run-id>/discovery.json` |
| Preserved report and status for this run | `PAYMENTS/runs/<run-id>/modernization_report.html` and `result.json` |
| Agent handoff, when generation is required | `PAYMENTS/runs/<run-id>/agent_request.json` |
| Generated jobs, runtime, DDL and dependencies | `PAYMENTS/targets/<language>-<database>/<artifact-id>/` |
| Local case outputs and execution evidence | `PAYMENTS/runs/<run-id>/verification/cases/<case-name>/` |
| Target history and source relationships | `PAYMENTS/target_registry.json` |

Files are created when their stage is reached. A blocked discovery run does not
claim to have generated code or test outputs. The report identifies what is ready
and what is missing. See **docs/MARKDOWN_INPUT.md** for dataset path examples.

Only three groups need your input: source/evidence gaps for mainframe SMEs;
installed SDK/driver/feed details for the local platform team; unresolved database
semantic differences for architecture review. Do not ask an SME to review Python.

## Working offline or through Artifactory

Framework tests and Python/SQLite need only Python's standard library. Generated
Java/C# Oracle/SQLite providers need the declared vendor artifacts. No public
feed is called automatically. NuGet sources are deliberately empty until an
approved source is supplied. See docs/OPERATING_TARGETS.md for exact setup/run
commands. Driver pins are not a completed transitive lock; capture the approved
resolved dependencies before deployment.
