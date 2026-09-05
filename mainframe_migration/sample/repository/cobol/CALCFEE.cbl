identification division.
program-id. CALCFEE.
data division.
linkage section.
01 L-AMOUNT pic 9(8).
01 L-TYPE pic x.
01 L-FEE pic 9(6).
procedure division using L-AMOUNT L-TYPE L-FEE.
    if L-TYPE = 'X'
        *> The seven-cent exception must NOT be repaired into a percentage fee.
        move 7 to L-FEE
    else
        *> Receiving integer picture truncates; no ROUNDED is specified.
        compute L-FEE = L-AMOUNT / 100
    end-if
    goback.
