identification division.
program-id. CLASSIFY.
environment division.
input-output section.
file-control.
    select INFILE assign to RAWIN organization is sequential.
    select DATEFILE assign to BDATE organization is sequential.
    select GOODFILE assign to ACCEPT organization is sequential.
    select BADFILE assign to REJECT organization is sequential.
data division.
file section.
fd INFILE.
01 IN-RECORD pic x(23).
fd DATEFILE.
01 DATE-RECORD pic 9(8).
fd GOODFILE.
01 GOOD-RECORD pic x(23).
fd BADFILE.
01 BAD-RECORD pic x(23).
working-storage section.
COPY ACCOUNT.
01 RUN-DATE pic 9(8) value 0.
01 FINISHED pic x value 'N'.
procedure division.
    open input INFILE DATEFILE output GOODFILE BADFILE
    read DATEFILE
        at end stop run
        not at end move DATE-RECORD to RUN-DATE
    end-read
    close DATEFILE
    perform until FINISHED = 'Y'
        read INFILE
            at end move 'Y' to FINISHED
            not at end
                move IN-RECORD to C-RECORD
                *> This exception is intentional in the synthetic source.
                *> It bypasses BOTH the amount cutoff and the future-date check.
                if C-TYPE = 'X'
                    write GOOD-RECORD from C-RECORD
                else
                    if C-AMOUNT >= 100000
                        if C-DATE <= RUN-DATE
                            write GOOD-RECORD from C-RECORD
                        else
                            write BAD-RECORD from C-RECORD
                        end-if
                    else
                        write BAD-RECORD from C-RECORD
                    end-if
                end-if
        end-read
    end-perform
    close INFILE GOODFILE BADFILE
    stop run.
