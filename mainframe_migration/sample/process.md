# Synthetic accounts process

This synthetic acceptance-test inventory contains the same five jobs and six steps
as `inventory.xlsx`. The supplied source repository and independently specified
synthetic case evidence define the behavior; this is not a mainframe baseline.

# Job: JOB001

## Classification

| Step | Program | Input | Output | Description |
|---|---|---|---|---|
| S010 | CLASSIFY | SAMPLE.RAW; SAMPLE.BDATE | SAMPLE.ACCEPT; SAMPLE.REJECT | Classify input accounts using the supplied source rules. |

# Job: JOB002

## Sorting

| Step | Program | Input | Output | Description |
|---|---|---|---|---|
| S010 | SORT | SAMPLE.ACCEPT | SAMPLE.SORTED | Sort accepted records according to the JCL controls. |

# Job: JOB003

## Fee processing

| Step | Program | Input | Output | Description |
|---|---|---|---|---|
| S010 | FEEPOST | SAMPLE.SORTED | SAMPLE.FEES | Calculate the source-defined fee records. |

# Job: JOB004

## Audit and database load

| Step | Program | Input | Output | Description |
|---|---|---|---|---|
| S010 | IEBGENER | SAMPLE.FEES | SAMPLE.AUDIT | Copy the fee records to the audit dataset. |
| S020 | LOADDB | SAMPLE.FEES | TABLE:ACCOUNT_LEDGER | Load the source-defined account ledger table. |

# Job: JOB005

## Totals

| Step | Program | Input | Output | Description |
|---|---|---|---|---|
| S010 | TOTALS | SAMPLE.FEES | SAMPLE.TOTAL | Produce the source-defined totals record. |
