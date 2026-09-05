-- Target: bigquery. Derived from source DDL, not from SQLite storage.

-- Execute with a configured default dataset. NOT ENFORCED is a capability gap, not equivalence.

CREATE TABLE `ACCOUNT_LEDGER` (
  `SEQ` INT64 NOT NULL,
  `ACCOUNT_ID` STRING(6) NOT NULL,
  `AMOUNT_CENTS` INT64 NOT NULL,
  `BUSINESS_DATE` INT64 NOT NULL,
  `CATEGORY` STRING(1) NOT NULL,
  `FEE_CENTS` INT64 NOT NULL,
  PRIMARY KEY (`SEQ`) NOT ENFORCED
);
