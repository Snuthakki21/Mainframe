"""JOB002 — migrated source job.
Run every JCL step in order and preserve the original business behavior.
Inputs/outputs are the source DD bindings; database access is selected separately.
Source: jcl/JOB002.jcl
"""
from decimal import Decimal, localcontext
from _runtime import Fields, relation

def step_S010(ctx):
    """Execute S010 / SORT with the original DD bindings."""
    dd = {'SORTIN': {'line': 3, 'dsn': 'SAMPLE.ACCEPT', 'disp': 'SHR'}, 'SORTOUT': {'line': 4, 'dsn': 'SAMPLE.SORTED', 'disp': '(NEW,CATLG,DELETE)'}, 'SYSIN': {'line': 5, 'inline': ' SORT FIELDS=(1,6,CH,A)\n OPTION EQUALS'}}
    ctx.sort(dd["SORTIN"], dd["SORTOUT"], [[1, 6, 'CH', 'A']], ctx.payload.get("max_sort_records", 100000))
    ctx.end_step()

def run(ctx):
    """Run all source steps; errors stop the job instead of skipping work."""
    with localcontext() as arithmetic:
        arithmetic.prec = 80
        step_S010(ctx)
        ctx.finish()
