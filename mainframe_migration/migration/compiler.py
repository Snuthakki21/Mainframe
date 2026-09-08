"""A deliberately bounded, source-driven offline translator.

This module makes the ZIP independently testable without an AI subscription. It
compiles a documented COBOL/JCL subset into ordinary Python functions; it never
copies a prewritten demo translation. Copilot/Devin handle broader source through
the sealed agent-artifact contract. An unknown construct raises AGENT_REQUIRED.
No source branch is removed merely because it looks odd or is absent from tests.
"""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
import json
import re
from .common import Blocked
from .discovery import resolve, source_lines

TOKEN = re.compile(r'\s+|"(?:[^"]|"")*"|\'(?:[^\']|\'\')*\'|>=|<=|<>|[A-Za-z][A-Za-z0-9_-]*|\d+(?:\.\d+)?|[.,():=+*/<>-]')

class Tokens:
    """Read every token; unfamiliar punctuation must not disappear during translation."""
    def __init__(self,text: str,source: str):
        self.source, self.items, self.pos = source, [], 0
        end = 0
        for match in TOKEN.finditer(text):
            if match.start() != end:
                raise Blocked(f'Unrecognized source text near {text[end:end+50]!r}.', 'AGENT_REQUIRED',source)
            end = match.end()
            if not match.group().isspace():
                self.items.append((match.group(),text.count('\n',0,match.start())+1))
        if text[end:].strip(): raise Blocked('Unrecognized trailing source text.', 'AGENT_REQUIRED',source)
    def peek(self) -> str:
        return self.items[self.pos][0].upper() if self.pos < len(self.items) else ''
    def raw(self) -> str:
        return self.items[self.pos][0] if self.pos < len(self.items) else ''
    def take(self, expected: str | None = None) -> str:
        if not self.peek(): raise Blocked('Unexpected end of source.', 'AGENT_REQUIRED',self.source)
        value = self.items[self.pos][0]
        if expected is not None and value.upper() != expected:
            raise Blocked(f'Expected {expected}, found {value}. This source form needs agent translation.', 'AGENT_REQUIRED',self.source)
        self.pos += 1
        return value.upper() if value[0] not in "\"'" else value
    def match(self,value: str) -> bool:
        if self.peek() == value: self.take(); return True
        return False
    def line(self) -> int:
        return self.items[self.pos][1] if self.pos < len(self.items) else (self.items[-1][1] if self.items else 1)

PRECEDENCE = {'OR':1,'AND':2,'=':3,'<>':3,'>':3,'<':3,'>=':3,'<=':3,'+':4,'-':4,'*':5,'/':5}

def literal(token: str):
    if token.startswith(('"',"'")): return token[1:-1].replace(token[0]*2,token[0])
    if token in {'ZERO','ZEROS','ZEROES'}: return Decimal(0)
    if token in {'SPACE','SPACES'}: return ' '
    try: return Decimal(token)
    except Exception: raise Blocked(f'Unsupported literal {token}.','AGENT_REQUIRED')

def expression(t: Tokens, minimum: int = 0) -> dict:
    token = t.take()
    if token == '(':
        left = expression(t); t.take(')')
    elif token in {'+','-'}:
        left = {'kind':'unary','op':token,'value':expression(t,6)}
    elif token.startswith(('"',"'")) or token[0].isdigit() or token in {'ZERO','ZEROS','ZEROES','SPACE','SPACES'}:
        value = literal(token)
        left = {'kind':'number' if isinstance(value,Decimal) else 'text','value':str(value)}
    elif re.fullmatch(r'[A-Z][A-Z0-9_-]*',token) and token not in {'IF','MOVE','READ','END-IF','NOT','EVALUATE'}:
        left = {'kind':'field','name':token}
    else: raise Blocked(f'Unsupported expression starting with {token}.','AGENT_REQUIRED',t.source)
    while t.peek() in PRECEDENCE and PRECEDENCE[t.peek()] >= minimum:
        op = t.take(); right = expression(t,PRECEDENCE[op]+1)
        left = {'kind':'binary','op':op,'left':left,'right':right}
    return left

BOUNDARIES = {'MOVE','COMPUTE','ADD','IF','ELSE','END-IF','READ','WRITE','OPEN','CLOSE','PERFORM','END-PERFORM','CALL','GOBACK','STOP','EXEC','AT','NOT','END-READ','END-COMPUTE','END-ADD','.'}

def _names(t: Tokens) -> list[str]:
    result = []
    while t.peek() and t.peek() not in BOUNDARIES:
        name = t.take()
        if not re.fullmatch(r'[A-Z][A-Z0-9_-]*',name): raise Blocked(f'Expected a field name, found {name}.','AGENT_REQUIRED',t.source)
        result.append(name)
    if not result: raise Blocked('A required field list is empty.','AGENT_REQUIRED',t.source)
    return result

def sequence(t: Tokens, stops: set[str], nested: bool = False) -> list[dict]:
    nodes = []
    while t.peek() and t.peek() not in stops:
        if t.peek() == '.':
            if nested: raise Blocked('A period terminates a nested scope. This source needs agent translation; its scope cannot be guessed.','AGENT_REQUIRED',t.source)
            t.take(); continue
        line, op = t.line(), t.take()
        node: dict = {'line':line,'kind':op.lower()}
        if op == 'IF':
            node['condition'] = expression(t)
            node['yes'] = sequence(t,{'ELSE','END-IF'},True)
            node['no'] = sequence(t,{'END-IF'},True) if t.match('ELSE') else []
            t.take('END-IF')
        elif op == 'PERFORM':
            t.take('UNTIL'); node['condition'] = expression(t)
            node['body'] = sequence(t,{'END-PERFORM'},True); t.take('END-PERFORM')
        elif op == 'MOVE':
            node['value'] = expression(t); t.take('TO'); node['targets'] = _names(t)
        elif op == 'COMPUTE':
            node['target'] = t.take(); t.take('='); node['value'] = expression(t); t.match('END-COMPUTE')
        elif op == 'ADD':
            node['value'] = expression(t); t.take('TO'); node['targets'] = _names(t); t.match('END-ADD')
        elif op == 'OPEN':
            entries, mode = [], ''
            while t.peek() and t.peek() not in BOUNDARIES:
                word = t.take()
                if word in {'INPUT','OUTPUT'}: mode = word
                elif mode: entries.append([mode,word])
                else: raise Blocked('Only explicit OPEN INPUT and OPEN OUTPUT are supported offline.','AGENT_REQUIRED',t.source)
            if not entries: raise Blocked('OPEN has no file.','AGENT_REQUIRED',t.source)
            node['files'] = entries
        elif op == 'CLOSE': node['files'] = _names(t)
        elif op == 'READ':
            node['file'] = t.take(); t.take('AT'); t.take('END')
            node['end'] = sequence(t,{'NOT','END-READ'},True)
            node['record'] = []
            if t.match('NOT'):
                t.take('AT'); t.take('END'); node['record'] = sequence(t,{'END-READ'},True)
            t.take('END-READ')
        elif op == 'WRITE':
            node['record'] = t.take()
            node['value'] = expression(t) if t.match('FROM') else None
        elif op == 'CALL':
            called = t.take()
            if not called.startswith(('"',"'")): raise Blocked('Dynamic CALL requires the complete possible target set.','DYNAMIC_CALL',t.source)
            node['program'] = literal(called).upper(); t.take('USING'); node['arguments'] = _names(t)
        elif op in {'GOBACK','STOP'}:
            if op == 'STOP': t.take('RUN')
            node['kind'] = 'return'; node['source_verb'] = op
        elif op == 'EXEC':
            t.take('SQL'); action = t.take()
            if action in {'COMMIT','ROLLBACK'}:
                t.match('WORK'); t.take('END-EXEC'); node['kind'] = action.lower()
            elif action == 'INSERT':
                t.take('INTO'); node['table'] = t.take(); t.take('(')
                columns = [t.take()]
                while t.match(','): columns.append(t.take())
                t.take(')'); t.take('VALUES'); t.take('(')
                values = []
                while True:
                    t.take(':'); values.append(t.take())
                    if not t.match(','): break
                t.take(')'); t.take('END-EXEC')
                if len(columns) != len(values): raise Blocked('SQL columns and host variables have different lengths.','AGENT_REQUIRED',t.source)
                node.update(kind='insert',columns=columns,values=values)
            else: raise Blocked(f'EXEC SQL {action} needs an agent-authored database implementation.','AGENT_REQUIRED',t.source)
        else:
            raise Blocked(f'Executable statement {op} at line {line} is not in the offline translator. It must be migrated, not skipped.','AGENT_REQUIRED',t.source)
        nodes.append(node)
    return nodes

def parse_statements(text: str, source: str) -> list[dict]:
    """Parse the entire procedure; a leftover statement is a blocker, never a comment."""
    t = Tokens(text,source)
    return sequence(t,set())

def expand(path: Path, index: dict, fmt: str, stack: tuple[Path,...] = ()) -> tuple[str,list[tuple[str,int]]]:
    if path in stack: raise Blocked('Circular COPY expansion requires review.','COPY_CYCLE',path.name)
    text, origins = [], []
    for filename,no,line in source_lines(path,fmt):
        if re.match(r'^\s*COPY\b',line,re.I):
            m = re.fullmatch(r'\s*COPY\s+[\'\"]?([A-Z0-9_-]+)[\'\"]?\s*\.\s*',line,re.I)
            if not m: raise Blocked('COPY REPLACING or continued COPY needs explicit agent expansion.','AGENT_REQUIRED',path.name)
            target = resolve(index,m.group(1),{'.cpy','.copy'})
            content, locations = expand(target,index,fmt,stack+(path,))
            text.extend(content.splitlines()); origins.extend(locations)
        else: text.append(line); origins.append((Path(filename).name,no))
    return '\n'.join(text), origins

def picture(text: str) -> tuple[str,int,int]:
    text = text.upper().replace(' ','')
    expanded = ''
    end = 0
    for m in re.finditer(r'([X9V])(?:\((\d+)\))?',text):
        if m.start() != end: raise Blocked(f'Unsupported picture {text}.','AGENT_REQUIRED')
        end = m.end(); count = int(m.group(2) or 1)
        if count > 32760: raise Blocked('Picture width exceeds the offline limit.','AGENT_REQUIRED')
        expanded += m.group(1)*count
    if end != len(text) or not expanded: raise Blocked(f'Unsupported picture {text}.','AGENT_REQUIRED')
    if set(expanded) == {'X'}: return 'text',len(expanded),0
    if re.fullmatch(r'9+(V9+)?',expanded):
        left, _, right = expanded.partition('V')
        if len(left+right)>31: raise Blocked('Numeric precision above 31 digits needs an explicit arithmetic profile.','AGENT_REQUIRED')
        return 'number',len(left+right),len(right)
    raise Blocked(f'Unsupported mixed picture {text}.','AGENT_REQUIRED')

def parse_layout(text: str, source: str, files: dict) -> list[dict]:
    """Build storage offsets for 01/05 DISPLAY layouts; reject redefinitions and tables."""
    t, segments, part = Tokens(text,source), [], []
    while t.peek():
        token = t.take()
        if token == '.': segments.append(part); part=[]
        else: part.append(token)
    if part: raise Blocked('Data declaration is missing its terminating period.','AGENT_REQUIRED',source)
    layout, root, offset, fd, names = [], '', 0, None, set()
    for words in segments:
        if not words: continue
        if words in [['DATA','DIVISION'],['FILE','SECTION'],['WORKING-STORAGE','SECTION'],['LINKAGE','SECTION']]:
            fd = None; continue
        if words[0] == 'FD':
            if len(words)!=2 or words[1] not in files: raise Blocked('FD options or an undeclared file need agent handling.','AGENT_REQUIRED',source)
            fd=words[1]; continue
        if words[0] not in {'01','05','1','5'} or len(words)<2:
            raise Blocked('Unsupported data declaration: '+' '.join(words), 'AGENT_REQUIRED',source)
        level, name = int(words[0]), words[1]
        if name in names: raise Blocked(f'Duplicate field {name} requires qualified-name resolution.','AGENT_REQUIRED',source)
        names.add(name)
        rest = words[2:]; value = None
        if 'VALUE' in rest:
            ix = rest.index('VALUE')
            if len(rest[ix+1:]) != 1: raise Blocked('Unsupported VALUE clause.','AGENT_REQUIRED',source)
            value = literal(rest[ix+1]); rest = rest[:ix]
        if rest:
            if rest[0] not in {'PIC','PICTURE'}: raise Blocked('Unsupported field clause: '+' '.join(rest),'AGENT_REQUIRED',source)
            kind,length,scale = picture(''.join(rest[1:]))
        else: kind,length,scale='group',0,0
        if level==1:
            root,offset=name,0
            if fd is not None:
                if 'record' in files[fd]: raise Blocked('Multiple records per FD need agent handling.','AGENT_REQUIRED',source)
                files[fd]['record']=name; fd=None
        elif not root: raise Blocked('A level-05 field has no level-01 group.','AGENT_REQUIRED',source)
        if level==5 and kind=='group': raise Blocked('Nested groups need agent handling.','AGENT_REQUIRED',source)
        item={'name':name,'root':root,'offset':offset,'length':length,'kind':kind,'scale':scale}
        if value is not None: item['value']=str(value)
        layout.append(item)
        offset += length
        if level==5:
            parent = next(x for x in layout if x['name']==root)
            if parent['kind']!='group': raise Blocked('Elementary 01 record has child declarations.','AGENT_REQUIRED',source)
            parent['length']=offset
    if any(x['length']==0 for x in layout): raise Blocked('A record has no known length.','AGENT_REQUIRED',source)
    for file in files.values():
        if 'record' not in file: raise Blocked('A SELECT has no matching FD record.','AGENT_REQUIRED',source)
    return layout

def program(name: str,index: dict,fmt: str) -> dict:
    path = resolve(index,name,{'.cbl','.cob','.cobol'})
    text, origins = expand(path,index,fmt)
    match = re.search(r'PROCEDURE\s+DIVISION(?:\s+USING\s+([A-Z0-9_\s-]+))?\s*\.',text,re.I)
    if not match: raise Blocked('PROCEDURE DIVISION is missing or has unsupported options.','AGENT_REQUIRED',path.name)
    before, body = text[:match.start()], text[match.end():]
    m = re.search(r'PROGRAM-ID\.\s*([A-Z0-9_-]+)\s*\.',before,re.I)
    if not m or m.group(1).upper()!=name: raise Blocked('PROGRAM-ID differs from the selected member.','AGENT_REQUIRED',path.name)
    header = before[:m.start()]
    if not re.fullmatch(r'\s*IDENTIFICATION\s+DIVISION\.\s*',header,re.I):
        raise Blocked('Identification/compiler directives need agent review.','AGENT_REQUIRED',path.name)
    rest = before[m.end():]
    d = re.search(r'\bDATA\s+DIVISION\.',rest,re.I)
    if not d: raise Blocked('DATA DIVISION is missing.','AGENT_REQUIRED',path.name)
    environment, data = rest[:d.start()], rest[d.start():]
    environment = re.sub(r'\b(?:ENVIRONMENT DIVISION|INPUT-OUTPUT SECTION|FILE-CONTROL)\s*\.','',environment,flags=re.I)
    files = {}
    pattern = re.compile(r'\bSELECT\s+([A-Z0-9_-]+)\s+ASSIGN\s+TO\s+([A-Z0-9_-]+)\s+ORGANIZATION\s+(?:IS\s+)?SEQUENTIAL\s*\.',re.I)
    for f in pattern.finditer(environment):
        file, dd = f.group(1).upper(),f.group(2).upper()
        if file in files: raise Blocked('Duplicate SELECT.','AGENT_REQUIRED',path.name)
        files[file]={'dd':dd}
    if pattern.sub('',environment).strip(): raise Blocked('Unsupported file-control/environment clause.','AGENT_REQUIRED',path.name)
    layout = parse_layout(data,path.name,files)
    tree = parse_statements(body,path.name)
    # Relate the generated statement to its physical source or expanded copybook line.
    base_line = text.count('\n',0,match.end())
    seq = 0
    def mark(nodes):
        nonlocal seq
        for node in nodes:
            seq+=1
            row = min(base_line+node['line']-1,len(origins)-1)
            original,line = origins[row]
            node['id']=f'{name}:{original}:{line}:{seq}'
            node['origin']=f'{original}:{line}'
            for key in ('yes','no','body','end','record'):
                if isinstance(node.get(key),list): mark(node[key])
    mark(tree)
    result={'name':name,'source':path.name,'layout':layout,'files':files,'tree':tree,
            'arguments':match.group(1).upper().split() if match.group(1) else [],'statements':seq,
            'working_storage':bool(re.search(r'WORKING-STORAGE\s+SECTION',data,re.I))}
    validate_program(result)
    return result

def walk(nodes):
    for node in nodes:
        yield node
        for key in ('yes','no','body','end','record'):
            if isinstance(node.get(key),list): yield from walk(node[key])

def validate_program(p: dict) -> None:
    """Resolve every field/file reference before executable Python is emitted."""
    names={f['name'] for f in p['layout']}
    def field(n):
        if n not in names: raise Blocked(f'{p["name"]} references unknown field {n}.','AGENT_REQUIRED',p['source'])
    def expr(e):
        if not e:return
        if e['kind']=='field':field(e['name'])
        elif e['kind']=='binary':expr(e['left']);expr(e['right'])
        elif e['kind']=='unary':expr(e['value'])
    for n in p['arguments']:field(n)
    for n in walk(p['tree']):
        k=n['kind']
        for key in ('condition','value'):
            if isinstance(n.get(key),dict):expr(n[key])
        for key in ('targets','arguments','values'):
            for name in n.get(key,[]):field(name)
        if 'target' in n:field(n['target'])
        if k=='write':field(n['record'])
        refs=[]
        if k=='open':refs=[x[1] for x in n['files']]
        elif k=='close':refs=n['files']
        elif k=='read':refs=[n['file']]
        for file in refs:
            if file not in p['files']:raise Blocked(f'Unknown SELECT file {file}.','AGENT_REQUIRED',p['source'])

def pyexpr(e: dict) -> str:
    kind=e['kind']
    if kind=='field': return f's.get({e["name"]!r})'
    if kind=='number': return f'Decimal({e["value"]!r})'
    if kind=='text': return repr(e['value'])
    if kind=='unary': return '('+e['op']+pyexpr(e['value'])+')'
    left,right,op=pyexpr(e['left']),pyexpr(e['right']),e['op']
    if op in {'=','<>','>','<','>=','<='}:return f'relation({left}, {op!r}, {right}, ctx.encoding)'
    return '('+left+' '+op.lower()+' '+right+')'

def funcname(name): return 'program_'+re.sub(r'[^a-zA-Z0-9_]','_',name)

def emit_program(p: dict) -> list[str]:
    """Emit readable statements and intent comments rather than hiding the job in eval."""
    args=p['arguments']; files=p['files']
    purpose=f'Run {p["name"]} from {p["source"]}; retain its conditions and exceptions.'
    lines=[f'def {funcname(p["name"])}(ctx, dd, arguments=()):',
           '    '+repr(purpose),
           '    s = Fields('+repr(p['layout'])+')','    streams = {}',
           f'    if len(arguments) != {len(args)}:',
           '        raise ValueError("CALL argument count does not match the source linkage.")']
    for i,name in enumerate(args): lines.append(f'    s.bind({name!r}, arguments[{i}])')
    ret='None'
    def add(indent,text):lines.append('    '*indent+text)
    def emit(nodes,indent):
        if not nodes:add(indent,'pass  # The source deliberately has no action in this branch.');return
        for n in nodes:
            k=n['kind'];add(indent,f'# Source {n["origin"]}: '+{'move':'copy the value using the receiving field width.',
                'compute':'perform the original calculation; do not change rounding.',
                'add':'add the stated value using the receiving field picture.',
                'if':'keep both outcomes of the source condition.',
                'perform':'repeat until the original end condition is true.',
                'read':'read one record and retain the explicit end-of-file behavior.',
                'write':'write the complete record without stripping characters.',
                'call':'run the called source program and keep its returned field values.',
                'insert':'insert the stated fields into the local test table.',
                'commit':'commit because the source explicitly requests it.',
                'rollback':'roll back because the source explicitly requests it.',
                'open':'open only the files named by this step.',
                'close':'close the files named by the source.',
                'return':'return exactly where the source ends this program.'}[k])
            add(indent,f'ctx.hit({n["id"]!r})')
            if k=='if':
                add(indent,'if '+pyexpr(n['condition'])+':');emit(n['yes'],indent+1)
                if n['no']:add(indent,'else:');emit(n['no'],indent+1)
            elif k=='perform':add(indent,'while not '+pyexpr(n['condition'])+':');emit(n['body'],indent+1)
            elif k in {'move','add'}:
                add(indent,'_value = '+pyexpr(n['value']))
                for target in n['targets']:
                    value='_value' if k=='move' else f's.get({target!r}) + _value'
                    add(indent,f's.set({target!r}, {value})')
            elif k=='compute':add(indent,f's.set({n["target"]!r}, {pyexpr(n["value"])})')
            elif k=='open':
                for mode,file in n['files']:
                    f=files[file]
                    add(indent,f'streams[{file!r}] = ctx.open(dd[{f["dd"]!r}], {mode!r}, s.length({f["record"]!r}))')
            elif k=='close':
                for file in n['files']:add(indent,f'streams[{file!r}].close()')
            elif k=='read':
                add(indent,f'_record = streams[{n["file"]!r}].read()')
                add(indent,'if _record is None:');emit(n['end'],indent+1)
                add(indent,'else:');add(indent+1,f's.set({files[n["file"]]["record"]!r}, _record)')
                if n['record']:emit(n['record'],indent+1)
            elif k=='write':
                matching=[name for name,f in files.items() if f['record']==n['record']]
                if len(matching)!=1:raise Blocked('WRITE record has no unique FD.','AGENT_REQUIRED',p['source'])
                if n['value']:add(indent,f's.set({n["record"]!r}, {pyexpr(n["value"])})')
                add(indent,f'streams[{matching[0]!r}].write(s.raw({n["record"]!r}))')
            elif k=='call':
                values='['+', '.join(f's.reference({name!r})' for name in n['arguments'])+']'
                add(indent,f'{funcname(n["program"])}(ctx, dd, {values})')
            elif k=='insert':
                values='['+', '.join(f's.get({name!r})' for name in n['values'])+']'
                add(indent,f'ctx.insert({n["table"]!r}, {n["columns"]!r}, {values})')
            elif k in {'commit','rollback'}:add(indent,f'ctx.{k}()')
            elif k=='return':add(indent,'return '+ret)
    emit(p['tree'],1);lines.append('    return '+ret);lines.append('')
    return lines

def sort_keys(step: dict) -> list[list]:
    sysin=step['dds'].get('SYSIN',{}).get('inline','')
    m=re.fullmatch(r'\s*SORT\s+FIELDS=\(([^)]+)\)\s+OPTION\s+EQUALS\s*',sysin,re.I)
    if not m:raise Blocked('Offline SORT requires explicit SORT FIELDS and OPTION EQUALS; other control cards need agent translation.','AGENT_REQUIRED',step['source'])
    pieces=[s.strip().upper() for s in m.group(1).split(',')]
    if len(pieces)%4:raise Blocked('SORT key is incomplete.','AGENT_REQUIRED',step['source'])
    result=[]
    for i in range(0,len(pieces),4):
        start,length,typ,direction=pieces[i:i+4]
        if not start.isdigit() or not length.isdigit() or int(start)<1 or int(length)<1 or typ not in {'CH','ZD'} or direction not in {'A','D'}:
            raise Blocked('SORT key type/order needs agent translation.','AGENT_REQUIRED',step['source'])
        result.append([int(start),int(length),typ,direction])
    return result

def compile_job(job: dict,index: dict,fmt: str) -> tuple[str,dict]:
    """Create one actual Python file for a job, including its statically called programs."""
    registry,active={},set()
    def check_called_program(p):
        # Do not reset persistent WORKING-STORAGE or treat STOP RUN like GOBACK.
        # The offline acceptance backend deliberately gates these broader semantics.
        if p['working_storage'] or p['files']:
            raise Blocked('Called-program storage/file lifetime needs a source-faithful agent implementation; it cannot be reset on every CALL.','AGENT_REQUIRED',p['source'])
        if any(n.get('source_verb')=='STOP' for n in walk(p['tree'])):
            raise Blocked('STOP RUN in a called program ends its run unit. Agent translation is required; it cannot be replaced by an ordinary function return.','AGENT_REQUIRED',p['source'])
    def load(name, is_call=False):
        if name in active:raise Blocked('Recursive CALL needs a source-backed storage/lifetime model.','AGENT_REQUIRED',name)
        if name in registry:
            if is_call:check_called_program(registry[name])
            return
        active.add(name);p=program(name,index,fmt)
        if is_call:check_called_program(p)
        for n in walk(p['tree']):
            if n['kind']=='call':load(n['program'],True)
        registry[name]=p;active.remove(name)
    for step in job['steps']:
        if step['program'] not in {'SORT','ICEMAN','IEBGENER','IEFBR14'}:load(step['program'])
    purpose='\n'.join([job['name']+' — generated behavior-preserving local job.',
           'Purpose: execute the source JCL steps below, in their original order.',
           'Inputs/outputs: the DD bindings in each step identify the datasets.',
           'Rules: preserve every parsed source branch, including unusual exceptions.',
           'Generated by the bounded offline translator; no business repair was applied.',
           'Validation and unsupported constructs are reported by the process runner.',
           'Source JCL: '+job['source']])
    # Provenance is data: quotes and Windows path escapes must remain literal.
    lines=[repr(purpose),'from decimal import Decimal, localcontext',
           'from migration.runtime import Fields, relation','']
    for p in registry.values():lines+=emit_program(p)
    for step in job['steps']:
        name='step_'+step['name'];pgm=step['program'];dd=step['dds']
        lines += [f'def {name}(ctx):',f'    """Execute {step["name"]}: {pgm}, using the original DD bindings."""',f'    dd = {dd!r}']
        if pgm in {'SORT','ICEMAN'}:
            if not {'SORTIN','SORTOUT','SYSIN'} <= set(dd):raise Blocked('SORT DD definitions are incomplete.','MISSING_DD',job['source'])
            keys=sort_keys(step)
            lines.append(f'    ctx.sort(dd["SORTIN"], dd["SORTOUT"], {keys!r}, ctx.payload.get("max_sort_records", 100000))')
        elif pgm=='IEBGENER':
            if not {'SYSUT1','SYSUT2'} <= set(dd):raise Blocked('IEBGENER DD definitions are incomplete.','MISSING_DD',job['source'])
            if 'SYSIN' in dd and not dd['SYSIN'].get('dummy'):raise Blocked('IEBGENER control statements need agent translation.','AGENT_REQUIRED',job['source'])
            lines.append('    ctx.copy(dd["SYSUT1"], dd["SYSUT2"])')
        elif pgm=='IEFBR14':
            raise Blocked('IEFBR14 allocation/deletion side effects need an explicit dataset lifecycle implementation.','AGENT_REQUIRED',job['source'])
        else:
            p=registry[pgm]
            for f in p['files'].values():
                if f['dd'] not in dd:raise Blocked(f'{pgm} requires DD {f["dd"]}, which is missing.','MISSING_DD',job['source'])
            lines.append(f'    {funcname(pgm)}(ctx, dd)')
        lines.append('    ctx.end_step()')
        lines.append('')
    lines += ['def run(ctx):','    """Run each JCL step once; errors stop the job rather than skipping work."""','    with localcontext() as arithmetic:','        arithmetic.prec = 80']
    for step in job['steps']:
        lines += [f'        print("STEP {job["name"]}/{step["name"]} — {step["program"]}", flush=True)',f'        step_{step["name"]}(ctx)']
    lines+=['        ctx.finish()','']
    trace={'job':job['name'],'mode':'bounded-source-compiler','sources':job['dependencies'],
           'statements':[{'id':n['id'],'source':n['origin'],'kind':n['kind']} for p in registry.values() for n in walk(p['tree'])],
           'steps':[s['name'] for s in job['steps']],'programs':list(registry)}
    text='\n'.join(lines)
    compile(text,job['name']+'.py','exec')
    return text,trace

def _split_columns(text: str) -> list[str]:
    result,start,depth=[],0,0
    for i,c in enumerate(text):
        if c=='(':depth+=1
        elif c==')':depth-=1
        elif c==',' and depth==0:result.append(text[start:i].strip());start=i+1
    result.append(text[start:].strip());return result

def translate_ddl(text: str) -> tuple[str,dict]:
    """Translate an explicit CREATE TABLE subset; missing constraints are not invented."""
    text=re.sub(r'--[^\n]*','',text)
    statements=[s.strip() for s in text.split(';') if s.strip()]
    output,schema=[],{}
    for statement in statements:
        m=re.fullmatch(r'CREATE\s+TABLE\s+([A-Z][A-Z0-9_]*)\s*\((.*)\)',statement,re.I|re.S)
        if not m:raise Blocked('DDL outside the explicit CREATE TABLE subset needs agent translation.','AGENT_REQUIRED','DDL')
        table,body=m.group(1).upper(),m.group(2)
        if table in schema:raise Blocked(f'Duplicate table definition {table}.','DDL')
        cols,parts,pk={},[],[]
        for column in _split_columns(body):
            pm=re.fullmatch(r'PRIMARY\s+KEY\s*\(([^)]+)\)',column,re.I)
            if pm:pk=[x.strip().upper() for x in pm.group(1).split(',')];continue
            cm=re.fullmatch(r'([A-Z][A-Z0-9_]*)\s+(INTEGER|SMALLINT|BIGINT|CHAR\s*\(\d+\)|VARCHAR\s*\(\d+\)|DECIMAL\s*\(\d+\s*,\s*\d+\))(\s+NOT\s+NULL)?',column,re.I)
            if not cm:raise Blocked(f'Unsupported DDL column/constraint: {column}. It will not be discarded.','AGENT_REQUIRED',table)
            name,typ,nonnull=cm.group(1).upper(),cm.group(2).upper(),bool(cm.group(3))
            if name in cols:raise Blocked(f'Duplicate column {table}.{name}.','DDL')
            if typ in {'INTEGER','SMALLINT','BIGINT'}:definition={'kind':'integer'};sqlite='INTEGER'
            elif typ.startswith('DECIMAL'):
                precision,scale=map(int,re.findall(r'\d+',typ))
                if not 0<=scale<=precision<=31:raise Blocked('Unsupported decimal precision.','AGENT_REQUIRED',table)
                definition={'kind':'decimal','precision':precision,'scale':scale};sqlite='TEXT'
            else:definition={'kind':'text','length':int(re.search(r'\d+',typ).group())};sqlite='TEXT'
            definition['nullable']=not nonnull;cols[name]=definition
            clause=f'"{name}" {sqlite}'+(' NOT NULL' if nonnull else '')
            if definition['kind']=='text':clause+=f' CHECK (length("{name}") <= {definition["length"]})'
            parts.append(clause)
        if not cols:raise Blocked('CREATE TABLE has no columns.','DDL',table)
        for c in pk:
            if c not in cols:raise Blocked('PRIMARY KEY refers to an unknown column.','DDL',table)
            if cols[c]['nullable']:raise Blocked('Primary key nullability must be explicit in the source DDL.','AGENT_REQUIRED',table)
        if pk:parts.append('PRIMARY KEY ('+', '.join('"'+x+'"' for x in pk)+')')
        schema[table]=cols
        output.append(f'CREATE TABLE "{table}" (\n  '+',\n  '.join(parts)+'\n);')
    return '-- SQLite local test DDL. Exact DECIMAL fields use decimal text storage.\n'+'\n\n'.join(output)+'\n',schema
