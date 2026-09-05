# Standing migration instructions

Preserve the behavior of supplied mainframe sources, including apparent business
bugs and deliberate exceptions. Do not repair the source or optimize its rules.
Do not automatically patch a failed generated candidate, alter expected outputs,
add missing commits, remove rejects, skip branches, or change comparison tolerances.
A separately authorized new attempt can restore equivalence, but is not automatic.

## Target authority

Read language and database only from the resolved target.json. Never hard-code
Python or SQLite as the future architecture. `dotnet` means C#/.NET, `bigquery`
means BigQuery, not an unspecified GCP service. Do not override selection because
a driver is missing. Report missing runtime/driver evidence instead.

The portable behavior model is source-linked. Do not make SQLite storage types,
or Python's accidental behavior, the specification for Java, C#, or Oracle.
Preserve source DDL, field precision, widths, encodings, transactions, and control
flow. Retarget using original sources, approved scoped knowledge, and intact
lineage. An older v1 delivery without this lineage is only a historical reference.

## Workflow

Follow .agents/skills/migrate-process/SKILL.md. Use local source files, no Git ops.
Discover what can be determined before asking the SME. Keep one consolidated
plain-English report. Document each job and function with its intent and source
references. Use deterministic local code for file/database comparisons, not AI
judgment over business records. Do not invent authoritative expected results.

The synthetic front end is not a universal compiler. Real-process agent generation
uses register-target with the complete selected native artifact and explicit
review/trace metadata. The request must match the current source and target.
Read-only adversarial review must seek omissions and changed behavior, not propose
business improvements. Label agent self-review as self-review, not third-party.

## Evidence and cost

Reuse unchanged models and language artifacts. A database-only change must not
force unnecessary source reanalysis. Never carry forward a passed result from
another target, changed test input, changed framework, or changed baseline.

Generated, compiled, contract-tested, live-database-tested, and organizationally
approved are different statuses. Missing SDKs mean not compiled. A contract replay
means not live database tested. Keep statements of completion tied to actual logs.
No deployment, driver installation, remote schema changes, or production execution
is performed by the default local flow. Approved Copilot use is already established.
