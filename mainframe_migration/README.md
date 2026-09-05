# Mainframe Migration Workbench v2 — configurable targets

Open **START_HERE.md**. Choose language and database in **target.json**.

This release separates source behavior, language code, database components, and
validation history. Python, C#/.NET, and Java are generation targets; SQLite,
Oracle, and BigQuery are independent database targets. Changing selection never
relabels an old validation result as a new target pass.

It is a bounded, tested workbench, not a universal COBOL compiler. General source
migration is driven by the approved Copilot/Devin agent. The deterministic
compiler is a synthetic acceptance-test backend. See the support matrix and the
actual release verification record before deciding what is ready.

## One normal command

```powershell
python modernize.py run --config "processes/PAYMENTS/process.json"
```

Use the one agent kickoff in START_HERE for discovery and code generation of a
real process. Internal registration commands are for the agent, not extra steps
for the operator. The local command never secretly invokes an AI endpoint.

## Select a target

Only change these two existing values in target.json; keep the remaining profile:

```json
"language": "java",
"database": "oracle"
```

Language: `python`, `dotnet` (C#), `java`. Database: `sqlite`, `oracle`, `bigquery`.
The word GCP is deliberately not accepted as a database name.

Source behavior models and language files have distinct fingerprints. Output
folders preserve prior generations. Tests run in fresh execution copies.

## Evidence labels

Generated is not compiled. Compiled is not database validated. Recording a database
operation is not running the selected database. Synthetic expectations are not a
mainframe baseline. Tests here ran on Linux; native Windows, live Copilot/Devin,
.NET compilation, JDBC driver execution, and live Oracle/BigQuery were not tested.

No source rule, sealed candidate, expected result, or comparison tolerance is
automatically repaired. Original source and fixed baseline hashes are checked.
