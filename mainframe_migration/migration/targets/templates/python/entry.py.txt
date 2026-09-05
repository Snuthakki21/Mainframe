"""Run one generated native Python job and report its actual outcome."""
from pathlib import Path
import importlib.util,json,sys,traceback
from _runtime import Context

def main():
    """The caller chooses a sealed job; this entry point never modifies its code."""
    job,context,result=sys.argv[1:4];payload=json.loads(Path(context).read_text(encoding='utf-8-sig'))
    ctx=None;status={'status':'FAILED','return_code':0,'events':{},'operations':[]}
    try:
        ctx=Context(payload)
        spec=importlib.util.spec_from_file_location('native_job',Path(__file__).parent/'jobs'/(job+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        returned=module.run(ctx)
        if returned is not None and type(returned) is not int:raise TypeError('Job return code must be an integer.')
        status.update(status='PASSED',return_code=returned or 0)
    except Exception as exc:status['error']=str(exc)
    finally:
        if ctx is not None:
            status['events']=dict(ctx.events);status['operations']=ctx.db.operations
            try:ctx.close()
            except Exception as exc:status.update(status='FAILED',error='Cleanup failed: '+str(exc))
        Path(result).write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    return 0 if status['status']=='PASSED' else 1
if __name__=='__main__':raise SystemExit(main())
