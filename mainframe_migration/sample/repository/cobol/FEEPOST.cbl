identification division.
program-id. FEEPOST.
environment division.
input-output section.
file-control.
    select INFILE assign to SORTED organization is sequential.
    select OUTFILE assign to FEES organization is sequential.
data division.
file section.
fd INFILE.
01 IN-RECORD pic x(23).
fd OUTFILE.
01 OUT-RECORD pic x(29).
working-storage section.
COPY ACCOUNT.
COPY FEE.
01 FINISHED pic x value 'N'.
procedure division.
    open input INFILE output OUTFILE
    perform until FINISHED = 'Y'
        read INFILE
            at end move 'Y' to FINISHED
            not at end
                move IN-RECORD to C-RECORD
                move C-RECORD to F-RECORD
                call 'CALCFEE' using C-AMOUNT C-TYPE F-FEE
                write OUT-RECORD from F-RECORD
        end-read
    end-perform
    close INFILE OUTFILE
    stop run.
