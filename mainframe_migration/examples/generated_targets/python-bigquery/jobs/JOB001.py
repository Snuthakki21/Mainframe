"""JOB001 — migrated source job.
Run every JCL step in order and preserve the original business behavior.
Inputs/outputs are the source DD bindings; database access is selected separately.
Source: jcl/JOB001.jcl
"""
from decimal import Decimal, localcontext
from _runtime import Fields, relation

def program_CLASSIFY(ctx, dd, arguments=()):
    """Run CLASSIFY from CLASSIFY.cbl; retain its conditions and exceptions."""
    s = Fields([{'name': 'IN-RECORD', 'root': 'IN-RECORD', 'offset': 0, 'length': 23, 'kind': 'text', 'scale': 0}, {'name': 'DATE-RECORD', 'root': 'DATE-RECORD', 'offset': 0, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'GOOD-RECORD', 'root': 'GOOD-RECORD', 'offset': 0, 'length': 23, 'kind': 'text', 'scale': 0}, {'name': 'BAD-RECORD', 'root': 'BAD-RECORD', 'offset': 0, 'length': 23, 'kind': 'text', 'scale': 0}, {'name': 'C-RECORD', 'root': 'C-RECORD', 'offset': 0, 'length': 23, 'kind': 'group', 'scale': 0}, {'name': 'C-ACCOUNT', 'root': 'C-RECORD', 'offset': 0, 'length': 6, 'kind': 'text', 'scale': 0}, {'name': 'C-AMOUNT', 'root': 'C-RECORD', 'offset': 6, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'C-DATE', 'root': 'C-RECORD', 'offset': 14, 'length': 8, 'kind': 'number', 'scale': 0}, {'name': 'C-TYPE', 'root': 'C-RECORD', 'offset': 22, 'length': 1, 'kind': 'text', 'scale': 0}, {'name': 'RUN-DATE', 'root': 'RUN-DATE', 'offset': 0, 'length': 8, 'kind': 'number', 'scale': 0, 'value': '0'}, {'name': 'FINISHED', 'root': 'FINISHED', 'offset': 0, 'length': 1, 'kind': 'text', 'scale': 0, 'value': 'N'}])
    streams = {}
    if len(arguments) != 0:
        raise ValueError("CALL argument count does not match the source linkage.")
    # Source CLASSIFY.cbl:25: open only the files named by this step.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:25:1')
    streams['INFILE'] = ctx.open(dd['RAWIN'], 'INPUT', s.length('IN-RECORD'))
    streams['DATEFILE'] = ctx.open(dd['BDATE'], 'INPUT', s.length('DATE-RECORD'))
    streams['GOODFILE'] = ctx.open(dd['ACCEPT'], 'OUTPUT', s.length('GOOD-RECORD'))
    streams['BADFILE'] = ctx.open(dd['REJECT'], 'OUTPUT', s.length('BAD-RECORD'))
    # Source CLASSIFY.cbl:26: read one record and retain the explicit end-of-file behavior.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:26:2')
    _record = streams['DATEFILE'].read()
    if _record is None:
        # Source CLASSIFY.cbl:27: return exactly where the source ends this program.
        ctx.hit('CLASSIFY:CLASSIFY.cbl:27:3')
        return None
    else:
        s.set('DATE-RECORD', _record)
        # Source CLASSIFY.cbl:28: copy the value using the receiving field width.
        ctx.hit('CLASSIFY:CLASSIFY.cbl:28:4')
        _value = s.get('DATE-RECORD')
        s.set('RUN-DATE', _value)
    # Source CLASSIFY.cbl:30: close the files named by the source.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:30:5')
    streams['DATEFILE'].close()
    # Source CLASSIFY.cbl:31: repeat until the original end condition is true.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:31:6')
    while not relation(s.get('FINISHED'), '=', 'Y', ctx.encoding):
        # Source CLASSIFY.cbl:32: read one record and retain the explicit end-of-file behavior.
        ctx.hit('CLASSIFY:CLASSIFY.cbl:32:7')
        _record = streams['INFILE'].read()
        if _record is None:
            # Source CLASSIFY.cbl:33: copy the value using the receiving field width.
            ctx.hit('CLASSIFY:CLASSIFY.cbl:33:8')
            _value = 'Y'
            s.set('FINISHED', _value)
        else:
            s.set('IN-RECORD', _record)
            # Source CLASSIFY.cbl:35: copy the value using the receiving field width.
            ctx.hit('CLASSIFY:CLASSIFY.cbl:35:9')
            _value = s.get('IN-RECORD')
            s.set('C-RECORD', _value)
            # Source CLASSIFY.cbl:38: keep both outcomes of the source condition.
            ctx.hit('CLASSIFY:CLASSIFY.cbl:38:10')
            if relation(s.get('C-TYPE'), '=', 'X', ctx.encoding):
                # Source CLASSIFY.cbl:39: write the complete record without stripping characters.
                ctx.hit('CLASSIFY:CLASSIFY.cbl:39:11')
                s.set('GOOD-RECORD', s.get('C-RECORD'))
                streams['GOODFILE'].write(s.raw('GOOD-RECORD'))
            else:
                # Source CLASSIFY.cbl:41: keep both outcomes of the source condition.
                ctx.hit('CLASSIFY:CLASSIFY.cbl:41:12')
                if relation(s.get('C-AMOUNT'), '>=', Decimal('100000'), ctx.encoding):
                    # Source CLASSIFY.cbl:42: keep both outcomes of the source condition.
                    ctx.hit('CLASSIFY:CLASSIFY.cbl:42:13')
                    if relation(s.get('C-DATE'), '<=', s.get('RUN-DATE'), ctx.encoding):
                        # Source CLASSIFY.cbl:43: write the complete record without stripping characters.
                        ctx.hit('CLASSIFY:CLASSIFY.cbl:43:14')
                        s.set('GOOD-RECORD', s.get('C-RECORD'))
                        streams['GOODFILE'].write(s.raw('GOOD-RECORD'))
                    else:
                        # Source CLASSIFY.cbl:45: write the complete record without stripping characters.
                        ctx.hit('CLASSIFY:CLASSIFY.cbl:45:15')
                        s.set('BAD-RECORD', s.get('C-RECORD'))
                        streams['BADFILE'].write(s.raw('BAD-RECORD'))
                else:
                    # Source CLASSIFY.cbl:48: write the complete record without stripping characters.
                    ctx.hit('CLASSIFY:CLASSIFY.cbl:48:16')
                    s.set('BAD-RECORD', s.get('C-RECORD'))
                    streams['BADFILE'].write(s.raw('BAD-RECORD'))
    # Source CLASSIFY.cbl:53: close the files named by the source.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:53:17')
    streams['INFILE'].close()
    streams['GOODFILE'].close()
    streams['BADFILE'].close()
    # Source CLASSIFY.cbl:54: return exactly where the source ends this program.
    ctx.hit('CLASSIFY:CLASSIFY.cbl:54:18')
    return None
    return None

def step_S010(ctx):
    """Execute S010 / CLASSIFY with the original DD bindings."""
    dd = {'RAWIN': {'line': 3, 'dsn': 'SAMPLE.RAW', 'disp': 'SHR'}, 'BDATE': {'line': 4, 'dsn': 'SAMPLE.BDATE', 'disp': 'SHR'}, 'ACCEPT': {'line': 5, 'dsn': 'SAMPLE.ACCEPT', 'disp': '(NEW,CATLG,DELETE)'}, 'REJECT': {'line': 6, 'dsn': 'SAMPLE.REJECT', 'disp': '(NEW,CATLG,DELETE)'}}
    program_CLASSIFY(ctx, dd)
    ctx.end_step()

def run(ctx):
    """Run all source steps; errors stop the job instead of skipping work."""
    with localcontext() as arithmetic:
        arithmetic.prec = 80
        step_S010(ctx)
        ctx.finish()
