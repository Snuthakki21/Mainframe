# v2 implementation and verification map

This is a completed work map, not a promise that all runtime environments passed.

| Requirement | Implementation | Evidence |
|---|---|---|
| Single language/database choice | targets/config.py, target.json | test_target_config |
| Reusable source meaning | targets/model.py | controller reuse/source-change tests |
| Original logical schema | targets/schema.py | test_portable_model |
| Native job code | targets/emit.py | test_generation, nine-target matrix |
| DB-specific components | targets/templates, package.py | database contract tests |
| Sealed history/artifacts | targets/controller.py | test_controller |
| Agent-selected targets | targets/agent.py | test_agent_targets |
| Separate execution statuses | targets/verify.py | test_verification and matrix |
| Packaged reproducibility | tools/verify_package.py | exact-ZIP receipt |

No Git operation was used. The original sample inputs, mainframe source fixture and
expected baseline are unchanged. The final release checksum and measured counts
are outside the ZIP in the accompanying verification report to avoid a self-hash
cycle. The internal package manifest covers all shipped files except itself.
