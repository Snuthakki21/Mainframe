# One Markdown input for each mainframe process

Save the process documentation as a UTF-8 `.md` file. A manual Team Composer
conversion of an existing workbook is a one-time preparation step. The framework
reads the saved Markdown directly on every run; it does not call Team Composer or
require Excel for Markdown input. Keep one file for the whole process, including
all its jobs and processing sections.

## Accepted format

Use a `# Job: JOBNAME` heading followed by one or more pipe tables. Processing
sections such as `## Input File Acquisition` or `## Customer Processing` can
introduce their own tables. Every step table needs `Step` and `Program`; add
`Input`, `Output` and/or `Description` as available.

```markdown
# PAYMENTS Job Flow Documentation

Source: PAYMENTS_steps.xlsx (one-time manual conversion)

# Job: PAYIN

| Step | Program | Input | Output |
|---|---|---|---|
| STEP0 | NONE | NONE | NONE |
| STEP010 | PAYREAD | BANK.PAYMENTS.RAW; BANK.BUSINESS.DATE | BANK.PAYMENTS.READY |

# Job: PAYPOST

## Posting

| Step | Program | Description |
|---|---|---|
| STEP020 | PAYWRITE | Apply the source-defined posting rules and create the audit output. |
```

Alternatively, a table can identify jobs in a `Job` column:

```markdown
| Job | Step | Program | Input | Output |
|---|---|---|---|---|
| PAYIN | STEP010 | PAYREAD | BANK.PAYMENTS.RAW<br>BANK.BUSINESS.DATE | BANK.PAYMENTS.READY |
| PAYPOST | STEP020 | PAYWRITE | BANK.PAYMENTS.READY | BANK.PAYMENTS.AUDIT |
```

These are format examples, not complete runnable business processes. Use the
source-backed [synthetic sample](../sample/process.md) to exercise the shipped
framework. [SN002DA-process.md](../examples/SN002DA-process.md) is an intentionally
incomplete illustration transcribed from the supplied screenshots.

| Input convention | Meaning |
|---|---|
| `# Job: JOBNAME` | Scope for following step tables. |
| Processing section heading | Preserved description of that part of the flow; it does not create a runtime branch. |
| `Step`, `Program` | Step identity and documented program or utility. Each job/step pair must be unique. |
| `Input`, `Output` | Documented dataset names; either column can be omitted. |
| `Description` | Documented intent retained for source review. |
| `NONE` | No program/dataset stated in that cell. It is not a member or dataset named NONE. |
| Semicolon or `<br>` inside an Input/Output cell | Separates multiple dataset names. |
| `#`, `$`, `@` inside a name | Part of the mainframe name, not a new Markdown heading. |
| Table separator row such as `\|---\|---\|---\|` | Required Markdown table structure. |

Keep each table row on one physical line in the `.md` file; the editor may wrap it
visually. Use `<br>` within a dataset cell for multiple entries. Use proper pipe
table separators after every header. An ambiguous or malformed step table must be
corrected instead of being treated as an empty process. Do not put the actual
inventory inside a Markdown code fence; the fences above are for documentation.

A placeholder such as `STEP0 | NONE | NONE | NONE` is preserved as documentation.
It does not create an executable no-op or permit a real source step to be omitted.
A Description-only row leaves datasets unspecified; discovery still reads JCL and
source dependencies. `NONE` in the documentation must be reconciled with source
evidence, not used to discard a source-declared file.

## Run the same framework

Give the agent the kickoff in [START_HERE.md](../START_HERE.md), containing the
process name, `.md` path, local source repository and available evidence. Select
the language and database in `target.json`. All nine existing combinations of
Python/C#/Java with SQLite/Oracle/BigQuery remain available.

For a new process, the agent initializes a configuration and performs discovery:

```powershell
python modernize.py init --process PAYMENTS --repository "C:\work\mainframe-source" --inventory "C:\work\process-inputs\PAYMENTS.md" --config "processes/PAYMENTS/process.json" --output "C:\work\migration-results"
```

`--output` is optional and is saved in the configuration. `--target` can optionally
select the target profile. Markdown does not need `--sheet`. Existing `.xlsx`
inventories still accept `--sheet Process` and their original five-column format.
`init` does not overwrite an existing process configuration. A missing-evidence
`BLOCKED` result after initialization is a discovery result to inspect, not proof
that the configuration was not created.

The agent fills in bindings and evidence it can establish, reads the current
request when native generation is needed, generates and registers the complete
candidate, and reruns the same command:

```powershell
python modernize.py run --config "processes/PAYMENTS/process.json"
```

The Python command performs deterministic local stages. The coding agent handles
real source analysis and generation in the existing agent session. No separate
model API or automatic Git operation is part of the local process run.

## Inputs, outputs and destinations

The inventory's Input/Output cells name logical mainframe datasets. Configure the
local mapping in `process.json`; do not turn a dataset name into a guessed path.
For example, these settings illustrate fixed-record bindings:

```json
{
  "datasets": {
    "BANK.PAYMENTS.RAW": {
      "role": "input",
      "path": "inputs/payments.bin",
      "format": "fixed",
      "encoding": "cp037",
      "record_length": 80
    },
    "BANK.PAYMENTS.AUDIT": {
      "role": "output",
      "path": "files/audit.bin",
      "format": "fixed",
      "encoding": "cp037",
      "record_length": 120
    }
  },
  "cases": [{
    "name": "normal",
    "path": "cases/normal",
    "expected_files": {
      "BANK.PAYMENTS.AUDIT": "expected/audit.bin"
    }
  }]
}
```

This is an illustrative configuration excerpt. The widths and encoding are not
defaults; replace them with the actual source definitions, include every required
dataset, and supply the remaining configuration and baseline evidence. For this
example:

| File | Destination |
|---|---|
| Supplied input | `<process-config-folder>/cases/normal/inputs/payments.bin` |
| Authoritative expected output | `<process-config-folder>/cases/normal/expected/audit.bin` |
| Actual generated audit output | `<output-root>/PAYMENTS/runs/<run-id>/verification/cases/normal/files/audit.bin` |

Intermediate outputs use the same per-case work directory. Expected outputs stay
in the supplied case evidence folder. Database table destinations come from
authoritative DDL and the selected target profile; a `TABLE:NAME` inventory entry
is a table reference, not a local file binding. Connection settings name environment
variables. The default run does not transfer files, create remote schemas, or run
production Oracle/BigQuery workloads.

The default `init`/`demo` output root is the framework's `output` folder. A configured
`output` path changes it for the process; `run --output` can override it for a run.
The following files are created as their stages are reached:

| Deliverable | Path under the output root |
|---|---|
| Current consolidated report | `PAYMENTS/modernization_report.html` |
| Current result for automation | `PAYMENTS/latest_result.json` |
| Parsed flow, documented datasets and configured destinations | `PAYMENTS/runs/<run-id>/process_flow.json` |
| Source dependency discovery | `PAYMENTS/runs/<run-id>/discovery.json` |
| Preserved per-run report and result | `PAYMENTS/runs/<run-id>/modernization_report.html`, `result.json` |
| Native generation request, when required | `PAYMENTS/runs/<run-id>/agent_request.json` |
| Sealed native artifact | `PAYMENTS/targets/<language>-<database>/<artifact-id>/` |
| Fresh compile/execution copy | `PAYMENTS/runs/<run-id>/verification/execution-copy/` |
| Per-case outputs, result files and execution logs | `PAYMENTS/runs/<run-id>/verification/cases/<case-name>/` |
| Target history | `PAYMENTS/target_registry.json` |

The sealed artifact contains native jobs, shared runtime and database adapter,
`database/schema.sql`, logical schema, dependency declarations, the resolved target
profile, package metadata and source lineage. A blocked run retains its available
report and discovery evidence without claiming that later-stage files exist.

## Evidence still required

Markdown establishes documented scope and intent. Complete JCL, programs,
copybooks, control members and DDL establish behavior. Scheduler evidence establishes
cross-job execution order; document order alone is not a scheduling contract.
File layouts and encodings establish data interpretation. Matched input bytes,
expected file/database results, return codes and mainframe run provenance establish
what can be compared.

The agent searches the supplied local sources before assembling one current list
of plain-English gaps in the report. A successful parse or generation is not a
claim that baseline comparison, native compilation or live database validation
passed. See [SUPPORT_AND_LIMITS.md](SUPPORT_AND_LIMITS.md).
