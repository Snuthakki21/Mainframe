"""Find the process's source trail before translating any business logic.

The inventory selects a process. JCL supplies actual step order and DD bindings.
COPY, literal CALL, EXEC SQL INCLUDE, and SQL table references extend the trail.
Ambiguous names, dynamic calls, unresolved members, and unsupported JCL are explicit
questions. This is conservative discovery, not a complete z/OS compiler or scheduler.
"""
from __future__ import annotations
from pathlib import Path
import re
from .common import Blocked, digest

EXTENSIONS = {'.cbl','.cob','.cobol','.cpy','.copy','.jcl','.proc','.sql','.ddl','.cntl','.ctl'}
UTILITIES = {'SORT','ICEMAN','IEBGENER','IEFBR14'}

def source_lines(path: Path, source_format: str = 'free') -> list[tuple[str, int, str]]:
    """Read explicit fixed/free source format; never guess columns from a filename."""
    result = []
    try: lines = path.read_text(encoding='utf-8-sig').splitlines()
    except UnicodeError as exc:
        raise Blocked('Source is not UTF-8 text. Supply the source encoding or a lossless UTF-8 export.', 'SOURCE_ENCODING', path.name) from exc
    for n, line in enumerate(lines, 1):
        if source_format == 'fixed':
            if len(line) >= 7 and line[6] in '*/': continue
            if len(line) >= 7 and line[6] not in ' ':
                raise Blocked(f'Fixed-format indicator {line[6]!r} on line {n} needs agent review (continuation/debug semantics).', 'AGENT_REQUIRED', path.name)
            line = line[7:72] if len(line) >= 7 else ''
        elif source_format != 'free':
            raise Blocked('Set source_format to fixed or free.', 'CONFIG')
        # Comments outside quoted strings are ignored, never quoted literal content.
        quote, cleaned, i = '', '', 0
        while i < len(line):
            char = line[i]
            if quote:
                cleaned += char
                if char == quote:
                    if i+1 < len(line) and line[i+1] == quote:
                        cleaned += line[i+1]; i += 1
                    else: quote = ''
            elif line[i:i+2] == '*>': break
            else:
                cleaned += char
                if char in "\"'": quote = char
            i += 1
        if cleaned.strip(): result.append((str(path), n, cleaned))
    return result

def build_index(repo: Path) -> dict[str, list[Path]]:
    """Index member names without choosing an arbitrary duplicate from the repository."""
    index: dict[str, list[Path]] = {}
    for path in sorted(repo.rglob('*')):
        if not path.is_file() or any(x in {'.git','.migration','output','__pycache__','.venv'} for x in path.relative_to(repo).parts): continue
        if path.suffix.lower() not in EXTENSIONS: continue
        if not path.resolve().is_relative_to(repo.resolve()):
            raise Blocked(f'Source link leaves the repository: {path.name}', 'UNSAFE_PATH')
        index.setdefault(path.stem.upper(), []).append(path)
    return index

def resolve(index: dict, name: str, suffixes: set[str] | None = None) -> Path:
    """Resolve a referenced member; missing or duplicate members are not interchangeable."""
    found = index.get(name.upper(), [])
    if suffixes: found = [p for p in found if p.suffix.lower() in suffixes]
    if not found: raise Blocked(f'{name} is referenced but its source is missing. Provide the member, or identify its authoritative external implementation and behavior.', 'MISSING_MEMBER', name)
    if len(found) != 1: raise Blocked(f'{name} has multiple source members: ' + ', '.join(str(p) for p in found) + '. Which one is used by this process?', 'AMBIGUOUS_MEMBER', name)
    return found[0]

def parse_jcl(text: str, source: str) -> dict:
    """Parse the supported explicit EXEC PGM/DD subset; all control flow is gated."""
    logical, inline, pending = [], False, None
    for no, line in enumerate(text.splitlines(), 1):
        if line.startswith('//*') or not line.strip(): continue
        if inline:
            if line.strip() == '/*': inline = False; continue
            if not line.startswith('//'):
                logical[-1]['inline'].append(line); continue
            inline = False
        if line.strip() in {'//','/*'}: continue
        if not line.startswith('//'):
            raise Blocked(f'Unrecognized JCL line {no}: {line[:80]}', 'AGENT_REQUIRED', source)
        match = re.match(r'^//([A-Z0-9@#$]*)\s+(JOB|EXEC|DD|SET|PROC|PEND|IF|ELSE|ENDIF|JCLLIB|INCLUDE)\b\s*(.*)$',line,re.I)
        if not match:
            if re.match(r'^//\s+', line) and logical and logical[-1]['args'].rstrip().endswith(','):
                logical[-1]['args'] += line[2:].strip(); continue
            raise Blocked(f'JCL line {no} cannot be interpreted safely: {line[:80]}', 'AGENT_REQUIRED', source)
        name, op, args = match.groups()
        logical.append({'name':name.upper(),'op':op.upper(),'args':args.strip(),'line':no,'inline':[]})
        inline = op.upper() == 'DD' and args.strip() in {'*','DATA'}
    jobs = [x for x in logical if x['op'] == 'JOB']
    if len(jobs) != 1: raise Blocked('Each selected JCL member must contain exactly one JOB statement.', 'AGENT_REQUIRED', source)
    job = {'name':jobs[0]['name'],'source':source,'steps':[]}
    step = None
    for item in logical:
        op, args, name = item['op'], item['args'], item['name']
        if op == 'JOB':
            if re.search(r'\b(RESTART|COND|TYPRUN)\s*=',args,re.I):
                raise Blocked('JOB-level conditional/restart behavior needs a source-faithful execution plan.', 'AGENT_REQUIRED',source)
            continue
        if '&' in args:
            raise Blocked(f'{name or op} contains JCL symbols. Provide their effective values or procedure/override sources.', 'JCL_SYMBOLS',source)
        if op not in {'EXEC','DD'}:
            raise Blocked(f'JCL {op} behavior must be expanded by the agent before execution; it cannot be skipped.', 'AGENT_REQUIRED',source)
        if op == 'EXEC':
            match = re.fullmatch(r'PGM=([A-Z0-9@#$_-]+)', args, re.I)
            if not match:
                raise Blocked(f'{name} has a procedure, condition, parameter, or execution option outside the offline subset: {args}', 'AGENT_REQUIRED',source)
            if any(s['name'] == name for s in job['steps']):
                raise Blocked(f'Duplicate JCL step {name}.', 'JCL',source)
            step = {'name':name,'program':match.group(1).upper(),'dds':{},'line':item['line'],'source':source}
            job['steps'].append(step)
        else:
            if step is None or not name or name in step['dds']:
                raise Blocked('DD concatenation or a DD outside a step needs agent review.', 'AGENT_REQUIRED',source)
            dd = {'line':item['line']}
            if args in {'*','DATA'}: dd['inline'] = '\n'.join(item['inline'])
            elif args == 'DUMMY': dd['dummy'] = True
            elif re.fullmatch(r'SYSOUT=\*',args,re.I): dd['sysout'] = True
            else:
                match = re.fullmatch(r"DSN=([A-Z0-9@#$._-]+),DISP=(SHR|OLD|NEW|MOD|\(NEW,CATLG,DELETE\))",args,re.I)
                if not match:
                    raise Blocked(f'{name} has unsupported DD allocation options: {args}. Supply effective dataset/record definitions.', 'AGENT_REQUIRED',source)
                dd.update(dsn=match.group(1).upper(),disp=match.group(2).upper())
                if dd['disp'] == 'MOD':
                    raise Blocked(f'{name} uses DISP=MOD. Append/restart behavior needs an explicit migration.', 'AGENT_REQUIRED',source)
            step['dds'][name] = dd
    if not job['steps']: raise Blocked('The job has no executable steps.', 'JCL',source)
    return job

def dependencies(path: Path, index: dict, source_format: str, seen: set[Path] | None = None) -> tuple[set[Path], list[dict], list[Blocked]]:
    """Follow static COPY/CALL/SQL references recursively, retaining every missing edge."""
    seen = set() if seen is None else seen
    if path in seen: return set(), [], []
    seen.add(path)
    found, edges, issues = {path}, [], []
    try: text = '\n'.join(x[2] for x in source_lines(path, source_format))
    except Blocked as e: return found, edges, [e]
    refs = []
    for match in re.finditer(r'\bCOPY\s+[\'\"]?([A-Z0-9_-]+)',text,re.I): refs.append(('COPY',match.group(1),{'.cpy','.copy'}))
    for match in re.finditer(r'\bCALL\s+([\'\"])([^\'\"]+)\1',text,re.I): refs.append(('CALL',match.group(2),{'.cbl','.cob','.cobol'}))
    if re.search(r'\bCALL\s+(?![\'\"])[A-Z]',text,re.I):
        issues.append(Blocked('A program name is chosen at run time. Provide the control values and possible called members.', 'DYNAMIC_CALL',path.name))
    for match in re.finditer(r'EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9_-]+)',text,re.I): refs.append(('SQL_INCLUDE',match.group(1),{'.cpy','.copy'}))
    for match in re.finditer(r'\b(?:FROM|JOIN|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([A-Z][A-Z0-9_.]*)',text,re.I):
        if 'EXEC SQL' in text.upper():
            edges.append({'from':path.name,'kind':'SQL_TABLE_CANDIDATE','to':match.group(1).upper()})
    for kind, name, suffixes in refs:
        edges.append({'from':path.name,'kind':kind,'to':name.upper()})
        try:
            dep = resolve(index,name,suffixes)
            files, more, problems = dependencies(dep,index,source_format,seen)
            found |= files; edges += more; issues += problems
        except Blocked as e: issues.append(e)
    return found, edges, issues

def discover(repo: Path, rows: list[dict], config: dict) -> dict:
    """Discover all selected jobs before returning the consolidated exception list."""
    index = build_index(repo)
    report = {'jobs':[], 'issues':[], 'edges':[], 'sources':{}, 'index':index}
    for name in dict.fromkeys(r['job'] for r in rows):
        selected = [r for r in rows if r['job'] == name]
        try:
            jcl = resolve(index,name,{'.jcl'})
            report['sources'][str(jcl.relative_to(repo))] = digest(jcl.read_bytes())
            job = parse_jcl(jcl.read_text(encoding='utf-8-sig'),str(jcl.relative_to(repo)))
            if job['name'] != name: raise Blocked(f'Inventory job {name} differs from JCL JOB {job["name"]}.', 'INVENTORY_CONFLICT',jcl.name)
            # Every JCL step must be visible. Missing inventory rows do not hide work.
            expected = [(r['step'],r['program']) for r in selected]
            actual = [(s['name'],s['program']) for s in job['steps']]
            if expected != actual:
                report['issues'].append(Blocked(f'Inventory steps {expected} differ from JCL steps {actual}. Confirm the process scope; no step will be silently dropped.', 'INVENTORY_CONFLICT',jcl.name).issue(name))
            files = {jcl}
            for step in job['steps']:
                if step['program'] in UTILITIES: continue
                try:
                    program = resolve(index,step['program'],{'.cbl','.cob','.cobol'})
                    members, edges, problems = dependencies(program,index,config.get('source_format','fixed'))
                    files |= members; report['edges'] += edges
                    report['issues'] += [e.issue(name) for e in problems]
                except Blocked as e: report['issues'].append(e.issue(name))
            for path in files:
                report['sources'][str(path.relative_to(repo))] = digest(path.read_bytes())
            job['dependencies'] = sorted(str(p.relative_to(repo)) for p in files)
            report['jobs'].append(job)
        except (Blocked, UnicodeError) as exc:
            e = exc if isinstance(exc,Blocked) else Blocked(str(exc),'SOURCE_ENCODING',name)
            report['issues'].append(e.issue(name))
    # Deduplication retains a stable ID; reading the same COPY twice is not two questions.
    report['issues'] = list({q['id']:q for q in report['issues']}.values())
    return report
