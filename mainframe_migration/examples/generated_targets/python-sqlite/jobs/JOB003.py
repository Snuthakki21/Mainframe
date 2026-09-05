"""JOB003 — migrated source job.
Run every JCL step in order and preserve the original business behavior.
Inputs/outputs are the source DD bindings; database access is selected separately.
Source: jcl/JOB003.jcl
"""
from decimal import Decimal, localcontext
from _runtime import Fields, relation

def program_CALCFEE(ctx, dd, arguments=()):
    """Run CALCFEE from CALCFEE.cbl; retain its conditions and exceptions."""
    s = Fields([{'name': 'L-AMOUNT', 'root': 'L-AMOUNT', 'offset': 0, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'L-TYPE', 'root': 'L-TYPE', 'offset': 0, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'L-FEE', 'root': 'L-FEE', 'offset': 0, 'length': 6, 'kind': 'number', 'scale': 0}])
    streams = {}
    if len(arguments) != 3:
        raise ValueError("CALL argument count does not match the source linkage.")
    s.bind('L-AMOUNT', arguments[0])
    s.bind('L-TYPE', arguments[1])
    s.bind('L-FEE', arguments[2])
    # Source CALCFEE.cbl:9: keep both outcomes of the source condition.
    ctx.hit('CALCFEE:CALCFEE.cbl:9:1')
    if relation(s.get('L-TYPE'), '=', 'X', ctx.encoding):
        # Source CALCFEE.cbl:11: copy the value using the receiving field width.
        ctx.hit('CALCFEE:CALCFEE.cbl:11:2')
        _value = Decimal('7')
        s.set('L-FEE', _value)
    else:
        # Source CALCFEE.cbl:14: perform the original calculation; do not change rounding.
        ctx.hit('CALCFEE:CALCFEE.cbl:14:3')
        s.set('L-FEE', (s.get('L-AMOUNT') / Decimal('100')))
    # Source CALCFEE.cbl:16: return exactly where the source ends this program.
    ctx.hit('CALCFEE:CALCFEE.cbl:16:4')
    return None
    return None

def program_FEEPOST(ctx, dd, arguments=()):
    """Run FEEPOST from FEEPOST.cbl; retain its conditions and exceptions."""
    s = Fields([{'name': 'IN-RECORD', 'root': 'IN-RECORD', 'offset': 0, 'length': 23, 'kind': 'text', 'scale': 0}, {'name': 'OUT-RECORD', 'root': 'OUT-RECORD', 'offset': 0, 'length': 29, 'kind': 'text', 'scale': 0}, {'name': 'C-RECORD', 'root': 'C-RECORD', 'offset': 0, 'length': 23, 'kind': 'group', 'scale': 0}, {'name': 'C-ACCOUNT', 'root': 'C-RECORD', 'offset': 0, 'length': 6, 'kind': 'text', 'scale': 0}, {'name': 'C-AMOUNT', 'root': 'C-RECORD', 'offset': 6, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'C-DATE', 'root': 'C-RECORD', 'offset': 14, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'C-TYPE', 'root': 'C-RECORD', 'offset': 22, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'F-RECORD', 'root': 'F-RECORD', 'offset': 0, 'length': 29, 'kind': 'group', 'scale': 0}, {'name': 'F-ACCOUNT', 'root': 'F-RECORD', 'offset': 0, 'length': 6, 'kind': 'text', 'scale': 0}, {'name': 'F-AMOUNT', 'root': 'F-RECORD', 'offset': 6, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-DATE', 'root': 'F-RECORD', 'offset': 14, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-TYPE', 'root': 'F-RECORD', 'offset': 22, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'F-FEE', 'root': 'F-RECORD', 'offset': 23, 'length': 6, 'kind': 'number', 'scale': 0}, {'name': 'FINISHED', 'root': 'FINISHED', 'offset': 0, 'length': 1, 'kind': 'text', 'scale': 0, 'value': 'N'}])
    streams = {}
    if len(arguments) != 0:
        raise ValueError("CALL argument count does not match the source linkage.")
    # Source FEEPOST.cbl:19: open only the files named by this step.
    ctx.hit('FEEPOST:FEEPOST.cbl:19:1')
    streams['INFILE'] = ctx.open(dd['SORTED'], 'INPUT', s.length('IN-RECORD'))
    streams['OUTFILE'] = ctx.open(dd['FEES'], 'OUTPUT', s.length('OUT-RECORD'))
    # Source FEEPOST.cbl:20: repeat until the original end condition is true.
    ctx.hit('FEEPOST:FEEPOST.cbl:20:2')
    while not relation(s.get('FINISHED'), '=', 'Y', ctx.encoding):
        # Source FEEPOST.cbl:21: read one record and retain the explicit end-of-file behavior.
        ctx.hit('FEEPOST:FEEPOST.cbl:21:3')
        _record = streams['INFILE'].read()
        if _record is None:
            # Source FEEPOST.cbl:22: copy the value using the receiving field width.
            ctx.hit('FEEPOST:FEEPOST.cbl:22:4')
            _value = 'Y'
            s.set('FINISHED', _value)
        else:
            s.set('IN-RECORD', _record)
            # Source FEEPOST.cbl:24: copy the value using the receiving field width.
            ctx.hit('FEEPOST:FEEPOST.cbl:24:5')
            _value = s.get('IN-RECORD')
            s.set('C-RECORD', _value)
            # Source FEEPOST.cbl:25: copy the value using the receiving field width.
            ctx.hit('FEEPOST:FEEPOST.cbl:25:6')
            _value = s.get('C-RECORD')
            s.set('F-RECORD', _value)
            # Source FEEPOST.cbl:26: run the called source program and keep its returned field values.
            ctx.hit('FEEPOST:FEEPOST.cbl:26:7')
            program_CALCFEE(ctx, dd, [s.reference('C-AMOUNT'), s.reference('C-TYPE'), s.reference('F-FEE')])
            # Source FEEPOST.cbl:27: write the complete record without stripping characters.
            ctx.hit('FEEPOST:FEEPOST.cbl:27:8')
            s.set('OUT-RECORD', s.get('F-RECORD'))
            streams['OUTFILE'].write(s.raw('OUT-RECORD'))
    # Source FEEPOST.cbl:30: close the files named by the source.
    ctx.hit('FEEPOST:FEEPOST.cbl:30:9')
    streams['INFILE'].close()
    streams['OUTFILE'].close()
    # Source FEEPOST.cbl:31: return exactly where the source ends this program.
    ctx.hit('FEEPOST:FEEPOST.cbl:31:10')
    return None
    return None

def step_S010(ctx):
    """Execute S010 / FEEPOST with the original DD bindings."""
    dd = {'SORTED': {'line': 3, 'dsn': 'SAMPLE.SORTED', 'disp': 'SHR'}, 'FEES': {'line': 4, 'dsn': 'SAMPLE.FEES', 'disp': '(NEW,CATLG,DELETE)'}}
    program_FEEPOST(ctx, dd)
    ctx.end_step()

def run(ctx):
    """Run all source steps; errors stop the job instead of skipping work."""
    with localcontext() as arithmetic:
        arithmetic.prec = 80
        step_S010(ctx)
        ctx.finish()
