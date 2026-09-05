# Independent synthetic baseline specification

These are made-up, non-bank examples. They are NOT outputs captured from IBM z/OS,
Db2, AutoSys, GnuCOBOL, Copilot, or Devin. The offline reference calculator was
written separately from the translator. It uses integer cents and an explicit
business specification, and does not import any migration module.

Input records are 23 bytes: account 6 text characters; amount 8 unsigned digits in
cents; date 8 YYYYMMDD digits; category 1 character. Files use EBCDIC code page 037,
fixed-length records, no record delimiter. The business date is an input file.

1. Category X is accepted even with an amount below the cutoff or a future date.
2. Otherwise accept only amount >= 100000 cents AND date <= supplied business date.
3. Reject output preserves the original relative order of rejected records.
4. Sort accepted records on the six-byte account, ascending, retaining equal-key order.
5. Fee is seven cents for X; otherwise integer division of amount cents by 100.
6. Fee output appends six fee digits; audit output is an exact copy.
7. Insert every fee record into ACCOUNT_LEDGER. Duplicate accounts are not collapsed.
   SEQ starts at 1; the pre-existing row with SEQ=0 must remain unchanged.
8. Total output has count 6 digits, total amount 12 digits, total fee 10 digits.
   Empty input produces a zero total record, empty outputs, and no new DB rows.

The unchanged original source encodes these same deliberately unusual rules. The
fixture writer is a development-only tool; normal runs never regenerate expected
results. A SHA-256 baseline manifest detects changed fixture bytes before a run.
