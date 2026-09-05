# Verification evidence

`v2` contains development checks, including intentional failing tests and their
passing regressions. They are not the final exact-ZIP release receipt. Some logs
retain development paths for auditability; executable code has no such paths.

The release verification report delivered alongside the ZIP records its exact
SHA-256 and extracted-package results. On your machine, VERIFY-WINDOWS.cmd writes
a new receipt under package-check. These mutable run files are not shipped as
active caches. The fresh sample is generated from source again.

Missing runtimes, recording-mode tests and live database tests have different
statuses. No Windows, .NET, remote Oracle/BigQuery, live Copilot/Devin, or native
IBM execution is implied by a Linux test log.
