# Durable SME answers

The file `answers.json` starts with an empty `answers` list. It belongs to this project, not a transient chat session. The agent records the exact answer you supply and its source.

An approved answer needs: `id` (question ID or stable fact ID), `scope` (exact process name or explicitly approved `global`), `answer` (plain English), `approved_by`, `evidence`, and `status: "approved"`. Unapproved drafts may remain in the file but do not affect generation. Do not fabricate the approver or approval.

Conflicting approved answers for the same ID/scope block the run. Changes to applicable approved answers invalidate cached generation. Answers do not automatically supply missing executable modules, verify a database definition, or bypass an unsupported runtime construct. The agent must apply evidence to the relevant configuration/source inventory without changing business behavior.

No framework command commits this file to Git. You retain the repository knowledge through your normal manual Git workflow.
