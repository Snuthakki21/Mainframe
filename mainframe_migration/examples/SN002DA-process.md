# SN002DA Job Flow Documentation — illustrative excerpt

This is a representative transcription of visible rows in the supplied screenshots
of a Team Composer conversion. It is intentionally incomplete, is not the original
converted file, and is not authoritative source code, scheduler evidence or a test
baseline. The complete original `.md`, JCL, programs, copybooks, layouts and matched
run evidence are still needed for a real migration. Dataset spellings below must
be checked against those sources.

Source noted in the screenshot: SN002DA_steps.xlsx.

---

# Job: ISNSOB

| Step | Program | Input | Output |
|---|---|---|---|
| STEP0 | NONE | NONE | NONE |
| STEP010 | SNB210 | NONE | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 |
| STEP020 | SNB215 | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 | NONE |
| STEP030 | IEBGENER | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 | INTSN.I.#SALES.SRECYCLE.R0008.D260821 |
| STEP040 | SORT | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 | INTSN.I.#RCYCL.SSORT200.R0008.D260821 |
| STEP050 | SNB200 | INTSN.I.#RCYCL.SSORT200.R0008.D260821 | INTSN.I.#RCYCL.AUMISMTCH.R0008.D260821 |
| STEP060 | SNRCUPDT | INTSN.I.#RCYCL.SINVEXTR.R0008.D260821 | NONE |

---

# Job: ISNBBGSA

## Input File Acquisition

| Step | Program | Output |
|---|---|---|
| STEPBLX | WEDELX | INTSN.I.#SALES.SBLBOOK.R0008.D260821 |
| STEPMSX | WEDELX | INTSN.I.#SALES.SMCBOOK.R0008.D260821 |
| STEPBBX | WEDELX | INTSN.I.#SALES.SBBBOOK.R0008.D260821 |

## Qualification Processing

| Step | Program | Description |
|---|---|---|
| STEP103 | SORT | Sort BB Book file. |
| STEP104 | SNQUALR4 | Qualify BB records and create BBAS qualified outputs. |
| STEP106 | SORT | Split MC Book records into qualified/non-qualified. |
| STEP107 | SNQUALR3 | Qualify MC records. |

## Feed Consolidation

| Step | Program | Description |
|---|---|---|
| STEP110 | SNFEEDRM | Consolidates partner/source feeds. |
| STEP111 | IEBGENER | Merges qualified name match files. |
| STEP112 | SORT | Split reference and sales-only records. |
| STEP113 | SORT | Deduplicate reference records. |
| STEP114 | IEBGENER | Create combined reference feed. |

## Customer Processing

| Step | Program | Description |
|---|---|---|
| STEP120 | SNB190 | Build customer combine dataset. |
| STEP140 | SORT | Sort combined feed. |
| STEP145 | SNECNSWK | Create customer relationship dataset. |
| STEP150 | SNCUSLES | Customer processing/audit creation. |
| STEP160 | SORT | Sort audit dataset. |
| STEP170 | SNB150 | New customer identification. |
| STEP190 | SORT | Prepare for mismatch processing. |
| STEP200 | SNB200 | AUM mismatch processing. |
| STEP210 | SNMAPRU1 | Mapping update. |
