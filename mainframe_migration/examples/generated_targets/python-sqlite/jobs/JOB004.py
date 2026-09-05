"""JOB004 — migrated source job.
Run every JCL step in order and preserve the original business behavior.
Inputs/outputs are the source DD bindings; database access is selected separately.
Source: jcl/JOB004.jcl
"""
from decimal import Decimal, localcontext
from _runtime import Fields, relation

def program_LOADDB(ctx, dd, arguments=()):
    """Run LOADDB from LOADDB.cbl; retain its conditions and exceptions."""
    s = Fields([{'name': 'IN-RECORD', 'root': 'IN-RECORD', 'offset': 0, 'length': 29, 'kind': 'text', 'scale': 0}, {'name': 'F-RECORD', 'root': 'F-RECORD', 'offset': 0, 'length': 29, 'kind': 'group', 'scale': 0}, {'name': 'F-ACCOUNT', 'root': 'F-RECORD', 'offset': 0, 'length': 6, 'kind': 'text', 'scale': 0}, {'name': 'F-AMOUNT', 'root': 'F-RECORD', 'offset': 6, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-DATE', 'root': 'F-RECORD', 'offset': 14, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'F-TYPE', 'root': 'F-RECORD', 'offset': 22, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'F-FEE', 'root': 'F-RECORD', 'offset': 23, 'length': 6, 'kind': 'number', 'scale': 0}, {'name': 'FINISHED', 'root': 'FINISHED', 'offset': 0, 'length': 1, 'kind': 'text', 'scale': 0, 'value': 'N'}, {'name': 'ROW-NUMBER', 'root': 'ROW-NUMBER', 'offset': 0, 'length': 6, 'kind': 'number', 'scale': 0, 'value': '0'}])
    streams = {}
    if len(arguments) != 0:
        raise ValueError("CALL argument count does not match the source linkage.")
    # Source LOADDB.cbl:16: open only the files named by this step.
    ctx.hit('LOADDB:LOADDB.cbl:16:1')
    streams['INFILE'] = ctx.open(dd['FEES'], 'INPUT', s.length('IN-RECORD'))
    # Source LOADDB.cbl:17: repeat until the original end condition is true.
    ctx.hit('LOADDB:LOADDB.cbl:17:2')
    while not relation(s.get('FINISHED'), '=', 'Y', ctx.encoding):
        # Source LOADDB.cbl:18: read one record and retain the explicit end-of-file behavior.
        ctx.hit('LOADDB:LOADDB.cbl:18:3')
        _record = streams['INFILE'].read()
        if _record is None:
            # Source LOADDB.cbl:19: copy the value using the receiving field width.
            ctx.hit('LOADDB:LOADDB.cbl:19:4')
            _value = 'Y'
            s.set('FINISHED', _value)
        else:
            s.set('IN-RECORD', _record)
            # Source LOADDB.cbl:21: copy the value using the receiving field width.
            ctx.hit('LOADDB:LOADDB.cbl:21:5')
            _value = s.get('IN-RECORD')
            s.set('F-RECORD', _value)
            # Source LOADDB.cbl:22: add the stated value using the receiving field picture.
            ctx.hit('LOADDB:LOADDB.cbl:22:6')
            _value = Decimal('1')
            s.set('ROW-NUMBER', s.get('ROW-NUMBER') + _value)
            # Source LOADDB.cbl:23: insert the stated fields into the local test table.
            ctx.hit('LOADDB:LOADDB.cbl:23:7')
            ctx.insert('ACCOUNT_LEDGER', ['SEQ', 'ACCOUNT_ID', 'AMOUNT_CENTS', 'BUSINESS_DATE', 'CATEGORY', 'FEE_CENTS'], [s.get('ROW-NUMBER'), s.get('F-ACCOUNT'), s.get('F-AMOUNT'), s.get('F-DATE'), s.get('F-TYPE'), s.get('F-FEE')])
    # Source LOADDB.cbl:31: close the files named by the source.
    ctx.hit('LOADDB:LOADDB.cbl:31:8')
    streams['INFILE'].close()
    # Source LOADDB.cbl:32: commit because the source explicitly requests it.
    ctx.hit('LOADDB:LOADDB.cbl:32:9')
    ctx.commit()
    # Source LOADDB.cbl:33: return exactly where the source ends this program.
    ctx.hit('LOADDB:LOADDB.cbl:33:10')
    return None
    return None

def step_S010(ctx):
    """Execute S010 / IEBGENER with the original DD bindings."""
    dd = {'SYSUT1': {'line': 3, 'dsn': 'SAMPLE.FEES', 'disp': 'SHR'}, 'SYSUT2': {'line': 4, 'dsn': 'SAMPLE.AUDIT', 'disp': '(NEW,CATLG,DELETE)'}, 'SYSIN': {'line': 5, 'dummy': True}}
    ctx.copy(dd["SYSUT1"], dd["SYSUT2"])
    ctx.end_step()

def step_S020(ctx):
    """Execute S020 / LOADDB with the original DD bindings."""
    dd = {'FEES': {'line': 7, 'dsn': 'SAMPLE.FEES', 'disp': 'SHR'}}
    program_LOADDB(ctx, dd)
    ctx.end_step()

def run(ctx):
    """Run all source steps; errors stop the job instead of skipping work."""
    with localcontext() as arithmetic:
        arithmetic.prec = 80
        step_S010(ctx)
        step_S020(ctx)
        ctx.finish()
