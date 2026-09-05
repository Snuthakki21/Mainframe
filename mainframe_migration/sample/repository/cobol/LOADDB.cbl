identification division.
program-id. LOADDB.
environment division.
input-output section.
file-control.
    select INFILE assign to FEES organization is sequential.
data division.
file section.
fd INFILE.
01 IN-RECORD pic x(29).
working-storage section.
COPY FEE.
01 FINISHED pic x value 'N'.
01 ROW-NUMBER pic 9(6) value 0.
procedure division.
    open input INFILE
    perform until FINISHED = 'Y'
        read INFILE
            at end move 'Y' to FINISHED
            not at end
                move IN-RECORD to F-RECORD
                add 1 to ROW-NUMBER
                exec sql
                    insert into ACCOUNT_LEDGER
                    (SEQ, ACCOUNT_ID, AMOUNT_CENTS, BUSINESS_DATE, CATEGORY, FEE_CENTS)
                    values
                    (:ROW-NUMBER, :F-ACCOUNT, :F-AMOUNT, :F-DATE, :F-TYPE, :F-FEE)
                end-exec
        end-read
    end-perform
    close INFILE
    exec sql commit end-exec
    stop run.
