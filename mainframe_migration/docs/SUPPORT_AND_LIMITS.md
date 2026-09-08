# Supported scope and non-equivalence boundaries

## Implemented in v2

UTF-8 Markdown process inventories with job headings, optional processing sections,
step/program tables containing input/output names and/or descriptions, and a
`Job`-column table alternative. `NONE` markers and multiple datasets separated by
semicolons or `<br>` are recognized. Parsed process flow and configured local
destinations are retained in `process_flow.json`. The existing `.xlsx` reader is
retained for compatibility. The sample now uses `sample/process.md` with the same
five jobs and six steps as its original workbook.

Independent Python/C#/Java and SQLite/Oracle/BigQuery configuration; source-linked
behavior models for the inherited synthetic subset; native language emitters;
separate database adapters and source-derived target DDL; immutable artifacts;
model/language cache reuse; target history and legacy-v1 recognition; candidate
registration for the coding-agent workflow; exact file/return-code comparisons;
actual Python/SQLite snapshots; explicit transaction-record replay; separate
compile, recording, live-database and baseline-origin statuses.

The source subset includes the supplied fixed-record unsigned DISPLAY layouts,
MOVE/COMPUTE/ADD, conditions/loops, sequential files, bounded sorts, CALL parameter
aliasing, copies and INSERT/COMMIT/ROLLBACK. The sample has five jobs and six steps.
Unsupported syntax is blocked rather than silently omitted.

## Execution evidence available in this build

Python compiled and executed for all selected databases; only SQLite used a real
database. Java compiled and executed for all selected databases in recording
mode, not with JDBC providers or live DBs. C# generated but NOT compiled or run:
no .NET SDK was available. No native Windows, live Copilot/Devin or IBM run occurred.
A local recording pass checks emitted application results and operation intent,
not driver/database semantics. The delivered exact-ZIP receipt is the authority
for measured test counts and actual environments.

## Not implemented or not validated

Automatic Team Composer conversion, OCR intake, or execution of instructions
embedded in a Markdown document. Save actual Markdown text after the one-time
conversion; screenshots show the format but are not executable process inputs.
Narrative descriptions do not supply missing program logic, file layouts,
authoritative output bytes, scheduler dependencies or production destinations.
Incomplete documentation is discovered and reported; accepting its syntax is not
a claim that the whole mainframe process can execute.

A universal Enterprise COBOL/JCL parser; complete PROC/symbol/conditional handling;
CICS/IMS/VSAM/GDG behavior; packed/binary/variable formats; all compiler settings;
general SELECT/UPDATE/DELETE/MERGE/cursors/SQLCODE/SQLSTATE/triggers/locking; complete
production transaction/restart behavior; automatic cloud deployment/provisioning;
a live Oracle/BigQuery state-comparison harness; full dependency locks from the
bank feed; performance/scale/resilience qualification; UI modernization; automatic
ETL generation; real physical data migration; organizational release approval.

The agent handoff does not magically remove these limits. Some source and schema
forms are still blocked before registration. An agent can only claim support after
implementing the missing contracts and passing appropriate independent evidence.

## Semantic blockers are not optional warnings

BigQuery primary keys are NOT ENFORCED. The sample source has an enforced primary
key, so BigQuery generations are flagged with a capability blocker even when the
recording tests pass. Oracle VARCHAR empty string vs NULL may require an explicit
source-backed mapping; it is not silently normalized. Decimals retain logical
precision/scale even when the local SQLite representation is TEXT.

## Evidence and trust

Checksums detect changed bytes, not a malicious actor authorized to rewrite both
code and manifests. Path checks are not a security sandbox. A reviewer string is
not proof of reviewer independence. This build's adversarial review was conducted
in the assistant session, not by an external third-party firm.

No regression sample proves all production inputs. Existing source quirks remain;
a discrepancy blocks validation rather than triggering repair. Original v1 artifacts
are recorded but not directly reinterpreted into new targets without source lineage.
