# Start here — one target file, one kickoff

## 1. Open the package

Extract `mainframe_migration` into your local working area. Open it in VS Code.
Keep using your manually cloned source repository. This framework never clones,
pulls, commits, creates branches, or pushes anything. Your existing approved
Copilot setup is used; the Python runner needs no separate model API key.

## 2. Test the package locally

Before editing target.json, in the terminal opened in the extracted folder, type:

```powershell
.\VERIFY-WINDOWS.cmd
```

The command checks the shipped file hashes, runs both regression suites, and
exercises all nine selections on a disposable copy of the sample. It records
missing SDKs/drivers separately; it never presents a skipped .NET or remote test
as passed. It does not change your central target choice or install packages.
Read the `evidence/package-check/.../verification.json` location printed at the end.

Python is required for the framework. Java/C# generation does not require those
SDKs, but native compilation does. The Java runtime uses an approved JDK; .NET
uses an approved matching SDK. The default native targets are Java 17 and net10.0.
This package was not executed on Windows during development.

## 3. Choose the target in one place

Open `target.json`. Change only the existing `language` and `database` values:

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

Paste the following in VS Code Copilot Agent mode or Devin. Replace the process
name and paths with your local values. There is no custom slash command dependency.

```text
Read AGENTS.md and .agents/skills/migrate-process/SKILL.md.
Migrate process PAYMENTS using the local repository C:\work\mainframe-source
and Excel inventory C:\work\inventory.xlsx, sheet Process.
Read language and database ONLY from target.json.
Create or reuse processes/PAYMENTS/process.json.
Discover dependencies from the source. Use the same source behavior, including
unusual exceptions; do not fix business rules or repair failed candidates.
Use available baseline evidence under C:\work\test-evidence.
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

The current report is:

```text
output/PAYMENTS/modernization_report.html
```

It links conceptually to generated jobs, selected DDL and dependencies in
`output/PAYMENTS/targets/<language>-<database>/<artifact fingerprint>/`.
`target_registry.json` remembers target history and source relationships.
Each run also retains its own report and machine-readable result under `runs/`.

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
