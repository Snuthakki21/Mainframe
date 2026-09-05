#!/usr/bin/env python3
"""Start the local workbench. One demo command performs generation, execution, and comparison.

For a real process, Copilot/Devin follows the repository skill and drives this same
runner. A plain Python command does not secretly invoke an unavailable AI service.
Use --help for exact commands. No Git operation or automatic code repair is done.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import platform
import sqlite3
import sys
import unittest

ROOT=Path(__file__).resolve().parent

def main(argv=None) -> int:
    """Choose the requested workflow and return a meaningful command exit code."""
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    demop=subs.add_parser('demo',help='Generate and validate the five-job sample using target.json.')
    demop.add_argument('--target',type=Path)
    demop.add_argument('--output',type=Path)
    demop.add_argument('--generate-only',action='store_true')
    runp=subs.add_parser('run',help='Run one configured process; unknown source emits an agent/SME request.')
    runp.add_argument('--config',type=Path,required=True);runp.add_argument('--discover-only',action='store_true')
    runp.add_argument('--output',type=Path)
    runp.add_argument('--target',type=Path)
    runp.add_argument('--generate-only',action='store_true')
    matrixp=subs.add_parser('verify-targets',help='Exercise the nine target combinations on disposable sample copies.')
    matrixp.add_argument('--output',type=Path,required=True)
    initp=subs.add_parser('init',help='Create a real-process configuration and immediately discover missing evidence.')
    initp.add_argument('--repository',type=Path,required=True)
    initp.add_argument('--inventory',type=Path,required=True)
    initp.add_argument('--process',required=True)
    initp.add_argument('--config',type=Path,required=True)
    initp.add_argument('--sheet',default='Process')
    initp.add_argument('--source-format',choices=['fixed','free'],default='fixed')
    subs.add_parser('doctor',help='Show the local Python and SQLite environment; do not install anything.')
    subs.add_parser('self-test',help='Run the shipped unit, integration, and adversarial tests.')
    reg=subs.add_parser('register',help='Seal an agent-generated candidate; no existing attempt is repaired.')
    for option in ('request','candidate','trace'):reg.add_argument('--'+option,type=Path,required=True)
    reg.add_argument('--job',required=True)
    reg2=subs.add_parser('register-target',help='Seal a complete selected-target candidate from the coding agent.')
    for option in ('request','candidate','review'):reg2.add_argument('--'+option,type=Path,required=True)
    args=parser.parse_args(argv)
    if sys.version_info<(3,10):
        print('Python 3.10 or later is required. Use the version approved for your laptop.');return 2
    if args.command=='doctor':
        print('Python:',platform.python_version());print('Executable:',sys.executable)
        print('Operating system:',platform.platform());print('SQLite:',sqlite3.sqlite_version)
        print('Mandatory third-party packages: none. No package installation or network call was made.')
        print('Copilot/Devin authentication and Windows policies are not tested by this command.');return 0
    if args.command=='self-test':
        suite=unittest.TestSuite()
        suite.addTests(unittest.TestLoader().discover(str(ROOT/'tests')))
        suite.addTests(unittest.TestLoader().discover(str(ROOT/'tests_target')))
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    from migration.targets.controller import run
    from migration.runner import register
    from migration.common import Blocked
    if args.command=='verify-targets':
        from migration.targets.matrix import exercise
        try:
            result=exercise(args.output);print('STATUS:',result['status']);return 0 if all(result['assertions'].values()) else 1
        except (Blocked,OSError,ValueError) as exc:print('BLOCKED:',exc);return 2
    if args.command=='register-target':
        from migration.targets.agent import register as register_target
        try:print(register_target(args.request,args.candidate,args.review));return 0
        except (Blocked,OSError,ValueError,SyntaxError) as exc:print('BLOCKED:',exc);return 2
    if args.command=='init':
        from migration.common import write_json
        from migration.inventory import read_inventory
        if args.config.exists():
            print('BLOCKED: configuration already exists; it will not be overwritten.');return 2
        try:
            rows=read_inventory(args.inventory,args.sheet)
            order=list(dict.fromkeys(r['job'] for r in rows))
            cfg={'schema_version':1,'generation_mode':'agent','process':args.process,
                'repository':str(args.repository.resolve()),'inventory':str(args.inventory.resolve()),
                'sheet':args.sheet,'source_format':args.source_format,'datasets':{},'cases':[],
                'execution_order':order,'order_evidence':'','baseline':{'kind':'mainframe'},
                'knowledge':str(ROOT/'knowledge/answers.json'),'output':str(ROOT/'output'),
                'cache':str(ROOT/'.migration/cache'),'agent_artifacts':str(ROOT/'agent_artifacts')}
            write_json(args.config,cfg)
            result=run(args.config);print('STATUS:',result['status']);return 2 if result['status']=='BLOCKED' else 0
        except (Blocked,OSError,ValueError) as exc:print('BLOCKED:',exc);return 2
    if args.command=='register':
        try:print(register(args.request,args.job,args.candidate,args.trace));return 0
        except (Blocked,OSError,ValueError) as exc:print('BLOCKED:',exc);return 2
    config=ROOT/'sample/process.json' if args.command=='demo' else args.config
    result=run(config,target_path=getattr(args,'target',None),output_override=getattr(args,'output',None),verify=not getattr(args,'generate_only',False),discover_only=getattr(args,'discover_only',False))
    print('STATUS:',result['status'])
    return 0 if result['status'] in {'SYNTHETIC_TARGET_VALIDATED','BASELINE_SCENARIOS_MATCHED','DISCOVERED','GENERATED_NOT_FULLY_VALIDATED','GENERATED_WITH_CAPABILITY_BLOCKERS'} else (1 if result['status']=='VALIDATION_FAILED' else 2)

if __name__=='__main__':raise SystemExit(main())
