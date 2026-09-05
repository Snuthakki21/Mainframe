# python / oracle generated artifact

This directory is an immutable generation result, not a production approval.
The same source behavior model is used for all targets. Jobs are native python
functions, one source file per job; they are not a wrapper around Python code.

Database schema: `database/schema.sql`. Schema requirements: `database/logical_schema.json`.
Check `database/capabilities.json` before execution. It may contain blocking
semantic differences even though code generation completed.

Dependencies are listed in `dependencies.json`. Use the approved Artifactory feed;
no public download or restore is performed by the generation workflow. Pinned
direct versions are not a full transitive dependency lock. Resolve and lock the
chosen drivers in the approved environment before deployment.

The workbench builds fresh execution copies and prepares the context JSON for
local validation. Never add build outputs or change source files in this sealed
folder. A failed candidate is reported, not automatically repaired.

Remote adapters are not exercised by local SQLite comparisons. BigQuery uses
short-lived bearer tokens supplied through the named environment variable; token
refresh and IAM setup remain external operational configuration. No automatic
DML retry is made after an uncertain remote outcome. Recorded job IDs support
manual reconciliation. Oracle expects the configured Easy Connect data source.

DDL is supplied for controlled deployment. The generated runner never creates,
drops, or resets Oracle/BigQuery objects. Local validation creates only fresh SQLite
files. Oracle/BigQuery integration needs separately provisioned test environments
and baseline evidence before it can receive a live-validation status.
