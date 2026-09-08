"""Emit source statements as native functions for the selected language.

The database is intentionally absent from emit_job. SQL operations call the
selected adapter through a stable contract. A database switch can therefore keep
identical job code without claiming the new database has already been validated.
"""
from __future__ import annotations
import json,re
from migration.compiler import emit_program,funcname
from migration.common import Blocked

COMMENTS={
'move':'Copy the source value using the receiving field width.',
'compute':'Apply the source calculation and its receiving field truncation.',
'add':'Add the source value without introducing a new rounding rule.',
'if':'Retain both source outcomes, including unusual exceptions.',
'perform':'Repeat until the original stopping condition is true.',
'read':'Read one complete record and keep the source end-of-file behavior.',
'write':'Write the complete record without trimming or deduplicating it.',
'open':'Open the files selected by this source step.',
'close':'Close exactly the files named by the source.',
'call':'Share caller storage with the called source program.',
'insert':'Insert the source columns through the selected database adapter.',
'commit':'Commit only because the source explicitly requests it.',
'rollback':'Roll back only because the source explicitly requests it.',
'return':'End this source program at the original return statement.'}

def name(value):
    """Map a source member to a legal native function suffix."""
    return re.sub(r'[^A-Za-z0-9_]','_',value)

def quote(value):
    """Use JSON-compatible escaped literals accepted by Java and C#."""
    return json.dumps(value,ensure_ascii=True)

def expr(e,lang):
    """Keep exact literals and explicit comparison/arithmetic rules in generated code."""
    k=e['kind']
    if k=='field':return 's.get('+quote(e['name'])+')'
    if k=='number':return ('new BigDecimal(' if lang=='java' else 'Dec.Parse(')+quote(e['value'])+')'
    if k=='text':return quote(e['value'])
    if k=='unary':return 'MfRuntime.math('+quote(e['op'])+', '+('BigDecimal.ZERO' if lang=='java' else 'Dec.Zero')+', '+expr(e['value'],lang)+')'
    op=e['op'];left=expr(e['left'],lang);right=expr(e['right'],lang)
    if op in {'AND','OR'}:return '(MfRuntime.truth('+left+') '+('&&' if op=='AND' else '||')+' MfRuntime.truth('+right+'))'
    if op in {'=','<>','>','<','>=','<='}:return 'ctx.relation('+left+', '+quote(op)+', '+right+')'
    return 'MfRuntime.math('+quote(op)+', '+left+', '+right+')'

def emit_job(model,language):
    """Generate one real source file per job. No interpretation of Python is used."""
    if language=='python':return emit_python(model)
    if language not in {'java','dotnet'}:raise Blocked('Unknown code target.','TARGET_CONFIG')
    java=language=='java';job=model['job'];lines=[]
    lines += ['/* '+job+' — behavior-preserving migrated job.',
              ' * Source: '+model['source'],
              ' * Purpose: run every source step in order; preserve unusual rules.',
              ' * Inputs and outputs: declared DD bindings in the sealed process model.',
              ' * SQL operations use the selected database adapter; no source repair is applied.', ' */']
    if java:lines+=['import java.util.*;','import java.math.BigDecimal;','']
    else:lines+=['using System;','using System.Collections.Generic;','']
    lines.append('public '+('final' if java else 'static')+' class '+job+' {')
    def add(i,s):lines.append('    '*i+s)
    throws=' throws Exception' if java else ''
    array=lambda items: ('new String[] {' if java else 'new string[] {')+', '.join(quote(x) for x in items)+'}'
    for p in model['programs']:
        add(1,'// Run '+p['name']+' from '+p['source']+'; do not simplify its conditions.')
        add(1,'static void '+funcname(p['name'])+'(MfRuntime.Context ctx, '+('Map<String,Object>' if java else 'Dictionary<string,object>')+' dd, MfRuntime.Ref[] arguments)'+throws+' {')
        add(2,'var s = new MfRuntime.Fields(ctx.layout('+quote(p['name'])+'));')
        add(2,('var streams = new HashMap<String,MfRuntime.RecordFile>();' if java else 'var streams = new Dictionary<string,MfRuntime.RecordFile>();'))
        add(2,'if (arguments.Length != '+str(len(p['arguments']))+') throw new Exception("CALL argument count differs from source linkage.");' if not java else 'if (arguments.length != '+str(len(p['arguments']))+') throw new IllegalArgumentException("CALL argument count differs from source linkage.");')
        for i,n in enumerate(p['arguments']):add(2,'s.bind('+quote(n)+', arguments['+str(i)+']);')
        getstream=lambda n: 'streams.get('+quote(n)+')' if java else 'streams['+quote(n)+']'
        dd=lambda n: 'MfRuntime.obj(dd.get('+quote(n)+'))' if java else 'MfRuntime.obj(dd['+quote(n)+'])'
        def emit(nodes,indent):
            if not nodes:add(indent,'// The source performs no action in this branch.');return
            for node in nodes:
                k=node['kind'];seq=node['id'].rsplit(':',1)[1]
                add(indent,'// '+node['origin']+': '+COMMENTS[k])
                add(indent,'ctx.hit('+quote(node['id'])+');')
                if k=='if':
                    add(indent,'if (MfRuntime.truth('+expr(node['condition'],language)+')) {');emit(node['yes'],indent+1)
                    if node['no']:add(indent,'} else {');emit(node['no'],indent+1)
                    add(indent,'}')
                elif k=='perform':
                    add(indent,'while (!MfRuntime.truth('+expr(node['condition'],language)+')) {');emit(node['body'],indent+1);add(indent,'}')
                elif k in {'move','add'}:
                    var='value_'+seq;add(indent,'var '+var+' = '+expr(node['value'],language)+';')
                    for n in node['targets']:
                        val=var if k=='move' else 'MfRuntime.math("+", s.get('+quote(n)+'), '+var+')'
                        add(indent,'s.set('+quote(n)+', '+val+');')
                elif k=='compute':add(indent,'s.set('+quote(node['target'])+', '+expr(node['value'],language)+');')
                elif k=='open':
                    for mode,f in node['files']:
                        x=p['files'][f];val='ctx.open('+dd(x['dd'])+', '+quote(mode)+', s.length('+quote(x['record'])+'))'
                        add(indent,'streams.put('+quote(f)+', '+val+');' if java else 'streams['+quote(f)+'] = '+val+';')
                elif k=='close':
                    for f in node['files']:add(indent,getstream(f)+'.close();')
                elif k=='read':
                    var='record_'+seq;add(indent,'var '+var+' = '+getstream(node['file'])+'.read();')
                    add(indent,'if ('+var+' == null) {');emit(node['end'],indent+1);add(indent,'} else {')
                    add(indent+1,'s.set('+quote(p['files'][node['file']]['record'])+', '+var+');');emit(node['record'],indent+1);add(indent,'}')
                elif k=='write':
                    f=next(n for n,d in p['files'].items() if d['record']==node['record'])
                    if node['value']:add(indent,'s.set('+quote(node['record'])+', '+expr(node['value'],language)+');')
                    add(indent,getstream(f)+'.write(s.raw('+quote(node['record'])+'));')
                elif k=='call':
                    args='new MfRuntime.Ref[] {'+', '.join('s.reference('+quote(n)+')' for n in node['arguments'])+'}'
                    add(indent,funcname(node['program'])+'(ctx, dd, '+args+');')
                elif k=='insert':
                    values=('new Object[] {' if java else 'new object[] {')+', '.join('s.get('+quote(n)+')' for n in node['values'])+'}'
                    add(indent,'ctx.insert('+quote(node['table'])+', '+array(node['columns'])+', '+values+');')
                elif k in {'commit','rollback'}:add(indent,'ctx.'+k+'();')
                elif k=='return':add(indent,'return;')
        emit(p['tree'],2);add(1,'}')
    for step in model['steps']:
        add(1,'// Execute '+step['name']+' ('+step['program']+') using the source DD bindings.')
        add(1,'static void step_'+name(step['name'])+'(MfRuntime.Context ctx)'+throws+' {')
        add(2,'var dd = ctx.dd('+quote(job)+', '+quote(step['name'])+');')
        d=lambda n: 'MfRuntime.obj(dd.get('+quote(n)+'))' if java else 'MfRuntime.obj(dd['+quote(n)+'])'
        if step['program'] in {'SORT','ICEMAN'}:
            keys=('new int[][] {' if java else 'new int[][] {')+', '.join('new int[] {'+','.join(map(str,[a,b,0 if typ=='CH' else 1,1 if direct=='D' else 0]))+'}' for a,b,typ,direct in step['sort_keys'])+'}'
            add(2,'ctx.sort('+d('SORTIN')+', '+d('SORTOUT')+', '+keys+');')
        elif step['program']=='IEBGENER':add(2,'ctx.copy('+d('SYSUT1')+', '+d('SYSUT2')+');')
        else:add(2,funcname(step['program'])+'(ctx, dd, new MfRuntime.Ref[0]);')
        add(2,'ctx.end_step();');add(1,'}')
    add(1,'// Run all source steps exactly once. A failure stops rather than skips work.')
    add(1,'public static void run(MfRuntime.Context ctx)'+throws+' {')
    for step in model['steps']:add(2,'step_'+name(step['name'])+'(ctx);')
    add(2,'ctx.finish();');add(1,'}');lines.append('}')
    return '\n'.join(lines)+'\n'

def emit_python(model):
    """Reuse the proved source emitter while removing its SQLite-specific import path."""
    purpose='\n'.join([model['job']+' — migrated source job.',
           'Run every JCL step in order and preserve the original business behavior.',
           'Inputs/outputs are the source DD bindings; database access is selected separately.',
           'Source: '+model['source']])
    lines=[repr(purpose),'from decimal import Decimal, localcontext','from _runtime import Fields, relation','']
    for p in model['programs']:lines+=emit_program(p)
    for step in model['steps']:
        lines += ['def step_'+name(step['name'])+'(ctx):',
                  '    """Execute '+step['name']+' / '+step['program']+' with the original DD bindings."""',
                  '    dd = '+repr(step['dds'])]
        if step['program'] in {'SORT','ICEMAN'}:lines.append('    ctx.sort(dd["SORTIN"], dd["SORTOUT"], '+repr(step['sort_keys'])+', ctx.payload.get("max_sort_records", 100000))')
        elif step['program']=='IEBGENER':lines.append('    ctx.copy(dd["SYSUT1"], dd["SYSUT2"])')
        else:lines.append('    '+funcname(step['program'])+'(ctx, dd)')
        lines+=['    ctx.end_step()','']
    lines+=['def run(ctx):','    """Run all source steps; errors stop the job instead of skipping work."""','    with localcontext() as arithmetic:','        arithmetic.prec = 80']
    for step in model['steps']:lines.append('        step_'+name(step['name'])+'(ctx)')
    lines+=['        ctx.finish()','']
    text='\n'.join(lines);compile(text,model['job']+'.py','exec');return text
