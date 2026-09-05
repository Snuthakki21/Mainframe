"""Execute one generated job as a separate, timed process.

This process is NOT a security sandbox. Its purpose is timeout/error isolation.
Results are written for the parent to compare; the worker cannot award validation.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import traceback
from .common import read_json,write_json
from .runtime import Context

def main() -> int:
    payload_file, code_file, result_file=map(Path,sys.argv[1:4])
    payload=read_json(payload_file)
    ctx=Context(payload)
    result={'status':'FAILED','events':{}}
    try:
        spec=importlib.util.spec_from_file_location('generated_job',code_file)
        if spec is None or spec.loader is None:raise ValueError('Generated job cannot be imported.')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        returned = module.run(ctx)
        if returned is not None and type(returned) is not int:
            raise ValueError('run(ctx) must return an integer job return code or None for zero.')
        result['return_code'] = 0 if returned is None else returned
        result['status']='PASSED'
    except Exception as exc:
        result['error']=str(exc);result['traceback']=traceback.format_exc()
    finally:
        result['events']=dict(ctx.events);ctx.close();write_json(result_file,result)
    return 0 if result['status']=='PASSED' else 1

if __name__=='__main__':raise SystemExit(main())
