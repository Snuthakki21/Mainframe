# Configuration reference

## One target authority

`target.json` contains schema_version 1, `language`, `database`, `versions`,
`validation`, `connections`, and `dependencies`. Unknown keys, duplicate keys,
unknown targets, wildcard driver versions, and inline connection secrets are
rejected. Accepted canonical targets are python/dotnet/java and
sqlite/oracle/bigquery. `.NET`, C# and csharp normalize to dotnet.

A process can use `target_file` to reference a central target profile relative to
the process configuration. Otherwise root target.json applies. The optional CLI
`--target` is an explicit override used by the test matrix; it is not a per-job
hidden setting. Process-level language/database/target fields are rejected to
avoid two competing sources of truth.

`versions.java_release`: 17, 21 or 25. `versions.dotnet_framework`: net8.0,
net9.0 or net10.0. Choose an installed approved SDK. Selecting a framework is not
proof the compiled application works on all those versions.

`validation.run_local` defaults true. False generates but does not compile/test.
Connection values name environment variables. The framework does not install
packages, resolve credentials, create remote tables or send production data.
Driver versions are direct pins; real target deployment needs an approved feed,
matching runtime/platform packages, and a resolved transitive lock.

## Process evidence

The existing schema_version 1 process structure is retained: repository,
inventory, source_format, collation, execution_order, order_evidence,
ddl_sources, datasets, cases, baseline, knowledge, output, cache, agent_artifacts.
`inventory` now normally points to a UTF-8 `.md` file. `sheet` is only used for
legacy `.xlsx` input and can be omitted for Markdown. Relative configuration paths
are resolved from the directory containing `process.json`.

For example, a configuration at `processes/PAYMENTS/process.json` can contain:

```json
{
  "inventory": "PAYMENTS.md",
  "repository": "../../../mainframe-source",
  "output": "../../output"
}
```

This is a path-settings excerpt, not a complete process configuration. Use
`modernize.py init --process PAYMENTS --repository <local-source-folder> --inventory <process.md> --config <process.json>`
to create the initial configuration and run discovery. Optional `--output` chooses
the persisted output root; optional `--target` selects a persisted target profile.
The normal later command remains `modernize.py run --config <process.json>`.
Initialization saves resolved absolute local paths. Initialize after placing the
framework beside the source repository on the work machine; update those paths
if the folders are relocated. Handwritten relative paths remain supported, as in
the portable shipped sample. If `output` is absent in a handwritten configuration,
it defaults to an `output` folder beside that configuration.

`execution_order` names every scoped job once. Inventory order seeds the initial
list for discovery; `order_evidence` must establish scheduler order before it is
accepted for execution. Headings and processing sections are documentation, not
new scheduling or branching rules.

Dataset paths are portable relative paths with forward slashes. Use explicit
encodings, fixed record lengths and input/output/intermediate roles. Input paths
are relative to each case's `path`; output and intermediate paths are relative to
that run's `verification/cases/<case-name>/` folder. `expected_files` paths are
relative to the case evidence directory. Destination names in the Markdown do not
create a filesystem binding or authorize a transfer; configure `datasets` using
source-backed names, layouts and local paths. See MARKDOWN_INPUT.md for an example.

The default generation_mode is `agent`. `offline_subset` is intentionally
restricted to synthetic baseline fixtures. `agent_generation_version` separates
explicitly authorized new candidate attempts; the agent must not increment it as
an automatic repair loop. A source or target change creates a different request.

Baseline manifests identify input bytes, expected bytes/database snapshots, and
initial database scripts. Mainframe evidence also needs run ID, source revision
and runtime context. No baseline is synthesized from generated outputs.

Markdown supports `# Job: JOBNAME` headings and pipe tables with `Step`, `Program`
and optional `Input`, `Output`, `Description` columns, or tables with a `Job` column.
`NONE` is an absence marker, not a dataset/program to fetch. Multiple dataset names
can be separated by semicolons or `<br>`. See MARKDOWN_INPUT.md for the full contract.

Legacy Excel columns remain A job, B step, C program, D inputs, E outputs. Neither
input format proves complete dependencies or runtime order. Current loader and
source-front-end limits are in SUPPORT_AND_LIMITS.md.
