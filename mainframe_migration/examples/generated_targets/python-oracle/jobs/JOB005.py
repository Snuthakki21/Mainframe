"""JOB005 — migrated source job.
Run every JCL step in order and preserve the original business behavior.
Inputs/outputs are the source DD bindings; database access is selected separately.
Source: jcl/JOB005.jcl
"""
from decimal import Decimal, localcontext
from _runtime import Fields, relation

def program_TOTALS(ctx, dd, arguments=()):
    """Run TOTALS from TOTALS.cbl; retain its conditions and exceptions."""
    s = Fields([{'name': 'IN-RECORD', 'root': 'IN-RECORD', 'offset': 0, 'length': 29, 'kind': 'text', 'scale': 0}, {'name': 'OUT-RECORD', 'root': 'OUT-RECORD', 'offset': 0, 'length': 28, 'kind': 'text', 'scale': 0}, {'name': 'F-RECORD', 'root': 'F-RECORD', 'offset': 0, 'length': 29, 'kind': 'group', 'scale': 0}, {'name': 'F-ACCOUNT', 'root': 'F-RECORD', 'offset': 0, 'length': 6, 'kind': 'text', 'scale': 0}, {'name': 'F-AMOUNT', 'root': 'F-RECORD', 'offset': 6, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-DATE', 'root': 'F-RECORD', 'offset': 14, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-TYPE', 'root': 'F-RECORD', 'offset': 22, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'F-FEE', 'root': 'F-RECORD', 'offset': 23, 'length': 6, 'kind': 'number', 'scale': 0}, {'name': 'FINISHED', 'root': 'FINISHED', 'offset': 0, 'length': 1, 'kind': 'text', 'scale': 0, 'value': 'N'}, {'name': 'TOTAL-RECORD', 'root': 'TOTAL-RECORD', 'offset': 0, 'length': 28, 'kind': 'group', 'scale': 0}, {'name': 'ITEM-COUNT', 'root': 'TOTAL-RECORD', 'offset': 0, 'length': 6, 'kind': 'number', 'scale': 0, 'value': '0'}, {'name': 'TOTAL-AMOUNT', 'root': 'TOTAL-RECORD', 'offset': 6, 'length': 12, 'kind': 'number', 'scale': 0, 'value': '0'}, {'name': 'TOTAL-FEE', 'root': 'TOTAL-RECORD', 'offset': 18, 'length': 10, 'kind': 'number', 'scale': 0, 'value': '0'}])
    streams = {}
    if len(arguments) != 0:
        raise ValueError("CALL argument count does not match the source linkage.")
    # Source TOTALS.cbl:22: open only the files named by this step.
    ctx.hit('TOTALS:TOTALS.cbl:22:1')
    streams['INFILE'] = ctx.open(dd['FEES'], 'INPUT', s.length('IN-RECORD'))
    streams['OUTFILE'] = ctx.open(dd['TOTAL'], 'OUTPUT', s.length('OUT-RECORD'))
    # Source TOTALS.cbl:23: repeat until the original end condition is true.
    ctx.hit('TOTALS:TOTALS.cbl:23:2')
    while not relation(s.get('FINISHED'), '=', 'Y', ctx.encoding):
        # Source TOTALS.cbl:24: read one record and retain the explicit end-of-file behavior.
        ctx.hit('TOTALS:TOTALS.cbl:24:3')
        _record = streams['INFILE'].read()
        if _record is None:
            # Source TOTALS.cbl:25: copy the value using the receiving field width.
            ctx.hit('TOTALS:TOTALS.cbl:25:4')
            _value = 'Y'
            s.set('FINISHED', _value)
        else:
            s.set('IN-RECORD', _record)
            # Source TOTALS.cbl:27: copy the value using the receiving field width.
            ctx.hit('TOTALS:TOTALS.cbl:27:5')
            _value = s.get('IN-RECORD')
            s.set('F-RECORD', _value)
            # Source TOTALS.cbl:28: add the stated value using the receiving field picture.
            ctx.hit('TOTALS:TOTALS.cbl:28:6')
            _value = Decimal('1')
            s.set('ITEM-COUNT', s.get('ITEM-COUNT') + _value)
            # Source TOTALS.cbl:29: add the stated value using the receiving field picture.
            ctx.hit('TOTALS:TOTALS.cbl:29:7')
            _value = s.get('F-AMOUNT')
            s.set('TOTAL-AMOUNT', s.get('TOTAL-AMOUNT') + _value)
            # Source TOTALS.cbl:30: add the stated value using the receiving field picture.
            ctx.hit('TOTALS:TOTALS.cbl:30:8')
            _value = s.get('F-FEE')
            s.set('TOTAL-FEE', s.get('TOTAL-FEE') + _value)
    # Source TOTALS.cbl:33: write the complete record without stripping characters.
    ctx.hit('TOTALS:TOTALS.cbl:33:9')
    s.set('OUT-RECORD', s.get('TOTAL-RECORD'))
    streams['OUTFILE'].write(s.raw('OUT-RECORD'))
    # Source TOTALS.cbl:34: close the files named by the source.
    ctx.hit('TOTALS:TOTALS.cbl:34:10')
    streams['INFILE'].close()
    streams['OUTFILE'].close()
    # Source TOTALS.cbl:35: return exactly where the source ends this program.
    ctx.hit('TOTALS:TOTALS.cbl:35:11')
    return None
    return None

def step_S010(ctx):
    """Execute S010 / TOTALS with the original DD bindings."""
    dd = {'FEES': {'line': 3, 'dsn': 'SAMPLE.FEES', 'disp': 'SHR'}, 'TOTAL': {'line': 4, 'dsn': 'SAMPLE.TOTAL', 'disp': '(NEW,CATLG,DELETE)'}}
    program_TOTALS(ctx, dd)
    ctx.end_step()

def run(ctx):
    """Run all source steps; errors stop the job instead of skipping work."""
    with localcontext() as arithmetic:
        arithmetic.prec = 80
        step_S010(ctx)
        ctx.finish()
