identification division.
program-id. TOTALS.
environment division.
input-output section.
file-control.
    select INFILE assign to FEES organization is sequential.
    select OUTFILE assign to TOTAL organization is sequential.
data division.
file section.
fd INFILE.
01 IN-RECORD pic x(29).
fd OUTFILE.
01 OUT-RECORD pic x(28).
working-storage section.
COPY FEE.
01 FINISHED pic x value 'N'.
01 TOTAL-RECORD.
   05 ITEM-COUNT pic 9(6) value 0.
   05 TOTAL-AMOUNT pic 9(12) value 0.
   05 TOTAL-FEE pic 9(10) value 0.
procedure division.
    open input INFILE output OUTFILE
    perform until FINISHED = 'Y'
        read INFILE
            at end move 'Y' to FINISHED
            not at end
                move IN-RECORD to F-RECORD
                add 1 to ITEM-COUNT
                add F-AMOUNT to TOTAL-AMOUNT
                add F-FEE to TOTAL-FEE
        end-read
    end-perform
    write OUT-RECORD from TOTAL-RECORD
    close INFILE OUTFILE
    stop run.
