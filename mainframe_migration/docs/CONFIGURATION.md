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
inventory, sheet, source_format, collation, execution_order, order_evidence,
ddl_sources, datasets, cases, baseline, knowledge, output, cache, agent_artifacts.
Dataset paths are portable relative paths with forward slashes; use explicit
encodings, fixed record lengths and input/output/intermediate roles.

The default generation_mode is `agent`. `offline_subset` is intentionally
restricted to synthetic baseline fixtures. `agent_generation_version` separates
explicitly authorized new candidate attempts; the agent must not increment it as
an automatic repair loop. A source or target change creates a different request.

Baseline manifests identify input bytes, expected bytes/database snapshots, and
initial database scripts. Mainframe evidence also needs run ID, source revision
and runtime context. No baseline is synthesized from generated outputs.

The Excel columns remain A job, B step, C program, D inputs, E outputs. The
workbook is a seed, not authoritative evidence of complete dependencies or runtime
order. Current loader and source-front-end limits are in SUPPORT_AND_LIMITS.md.
