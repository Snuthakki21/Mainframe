# Native target handoff

## What this interface does

It lets the approved IDE/Devin agent submit actual Python, Java or C# sources for
the selected database. No model API is embedded. The local runner issues
`agent_request.json`; the same agent session generates and registers the candidate
then invokes validation. Contract tests do not constitute a live agent test.

## Candidate layout

All candidates include package.json, target.json, README.md, dependencies.json,
database/schema.sql, database/logical_schema.json, database/capabilities.json,
and one jobs/JOB file with .py, .java or .cs extension matching the target.
Python uses `_entry.py JOB context.json result.json`; Java uses
`Main JOB context.json result.json`; .NET uses the built `MigratedProcess.dll`
with those arguments. Shared runtimes and native project/build files are included.

The package metadata includes language, database, source-linked job models,
source logical schema, datasets, execution_order, codepage tables, connections,
and computed capability blockers. The request contains authoritative schema,
source file hashes, job dependencies, approved answers, target configuration,
and eligible prior same-language artifacts. A candidate must not change these
contracts or suppress capability blockers.

Generated adapters implement the INSERT/COMMIT/ROLLBACK subset. General queries,
updates, deletes, cursor/error behavior and JCL extensions need new implemented
contracts and tests, not declarations that an unsupported operation passed.

## Review JSON

Create a real review using the request's ID. This is the expected shape; source
and generated locations must be actual existing lines:

```json
{
  "request_id": "the exact ID from agent_request.json",
  "reviewer": "reviewer's identity or agent/session identity",
  "method": "agent_self_review",
  "unresolved_fidelity_findings": [],
  "jobs": {
    "JOB001": {
      "source_paths": ["jcl/JOB001.jcl", "cobol/CLASSIFY.cbl", "copybooks/ACCOUNT.cpy"],
      "trace": [{
        "source": "cobol/CLASSIFY.cbl",
        "source_line": 39,
        "generated_file": "jobs/JOB001.py",
        "generated_line": 50,
        "intent": "Keep the exception category's original bypass behavior."
      }]
    }
  }
}
```

The illustration is a format example, not a preapproved review or executable
candidate. Every selected job and dependency must be represented. Allowed method
labels are agent_self_review, separate_agent_review and human_review. The tool
checks structure, references, source/target binding and sealed bytes; it cannot
prove a natural-language review is correct. Runtime comparison is separate.

`python modernize.py register-target --request RUN/agent_request.json --candidate CANDIDATE --review REVIEW.json`

Registration rejects stale source/target snapshots, missing native files, missing
source references, changed logical schema, mismatched DDL, suppressed blockers,
and replacement of a sealed candidate. Runtime checking is performed by the next
normal run and never edits the candidate. Existing v1 `register` is a legacy
Python interface retained only for compatibility; use register-target for v2.
