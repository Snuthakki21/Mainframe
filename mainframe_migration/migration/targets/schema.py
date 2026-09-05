"""Keep logical database requirements separate from a database's storage syntax.

The original DDL is the evidence. In particular, a SQLite TEXT column must not
become the source of truth for a decimal when a process is retargeted. This
parser accepts an explicit subset and rejects any constraint it cannot retain.
"""
from __future__ import annotations
import re
from decimal import Decimal,localcontext
from migration.common import Blocked
from migration.compiler import _split_columns

BOUNDS={'SMALLINT':(-32768,32767),'INTEGER':(-2147483648,2147483647),'BIGINT':(-9223372036854775808,9223372036854775807)}

def ident(value: str) -> str:
    """Accept only simple source identifiers; do not interpolate arbitrary SQL text."""
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',value):
        raise Blocked('A database identifier needs explicit quoting/name mapping: '+str(value), 'SQL_IDENTIFIER')
    return value

def parse_schema(text: str) -> dict:
    """Read source column types, declared order, nullability, bounds, and primary keys."""
    text=re.sub(r'--[^\n]*','',text);result={}
    for stmt in (s.strip() for s in text.split(';') if s.strip()):
        m=re.fullmatch(r'CREATE\s+TABLE\s+([A-Z][A-Z0-9_]*)\s*\((.*)\)',stmt,re.I|re.S)
        if not m:raise Blocked('DDL is outside the implemented CREATE TABLE subset; it cannot be inferred from SQLite.', 'AGENT_REQUIRED','DDL')
        table=ident(m.group(1).upper())
        if table in result:raise Blocked('Duplicate table '+table,'DDL')
        cols={};pk=[]
        for column in _split_columns(m.group(2)):
            p=re.fullmatch(r'PRIMARY\s+KEY\s*\(([^)]+)\)',column,re.I)
            if p:
                if pk:raise Blocked('More than one primary key declaration.','DDL',table)
                pk=[ident(x.strip().upper()) for x in p.group(1).split(',')];continue
            c=re.fullmatch(r'([A-Z][A-Z0-9_]*)\s+(SMALLINT|INTEGER|BIGINT|CHAR\s*\(\d+\)|VARCHAR\s*\(\d+\)|DECIMAL\s*\(\d+\s*,\s*\d+\))(\s+NOT\s+NULL)?',column,re.I)
            if not c:raise Blocked('Unsupported column or constraint: '+column+'. It will not be dropped.', 'AGENT_REQUIRED',table)
            name=ident(c.group(1).upper());typ=re.sub(r'\s+','',c.group(2).upper())
            if name in cols:raise Blocked('Duplicate column '+name,'DDL',table)
            col={'name':name,'nullable':not bool(c.group(3)),'source_type':typ.split('(')[0]}
            if typ in BOUNDS:
                lo,hi=BOUNDS[typ];col.update(kind='integer',minimum=str(lo),maximum=str(hi))
            elif typ.startswith('DECIMAL'):
                precision,scale=map(int,re.findall(r'\d+',typ))
                if not 1<=precision<=31 or not 0<=scale<=precision:raise Blocked('Unsupported decimal precision/scale.','AGENT_REQUIRED',table)
                col.update(kind='decimal',precision=precision,scale=scale)
            else:
                length=int(re.search(r'\d+',typ).group())
                if length<1:raise Blocked('Zero-width text is not a valid source column.','DDL',table)
                col.update(kind='text',length=length)
            cols[name]=col
        if not cols:raise Blocked('Table has no columns.','DDL',table)
        if len(pk)!=len(set(pk)):raise Blocked('Primary key has repeated columns.','DDL',table)
        for name in pk:
            if name not in cols or cols[name]['nullable']:raise Blocked('Primary key columns need explicit non-null definitions.','AGENT_REQUIRED',table)
        result[table]={'columns':cols,'primary_key':pk,'column_order':list(cols)}
    return result

def capabilities(schema: dict,database: str) -> list[dict]:
    """Report requirements the selected database cannot preserve automatically.

    Generation may still be useful for review. These items are execution blockers,
    not warnings that an agent may waive merely to get a green report.
    """
    issues=[]
    for table,spec in schema.items():
        if database=='bigquery' and spec['primary_key']:
            issues.append({'code':'PRIMARY_KEY_NOT_ENFORCED','table':table,'question':f'{table} requires enforced primary-key uniqueness. BigQuery does not enforce keys. A reviewed enforcement architecture is required; the framework will not drop this requirement.'})
        for name,col in spec['columns'].items():
            if database=='oracle' and col['source_type']=='VARCHAR':
                issues.append({'code':'EMPTY_STRING_SEMANTICS','table':table,'question':f'{table}.{name} is variable text. Oracle treats empty strings as NULL; provide a source-backed representation decision before execution.'})
            if database=='oracle' and col['kind']=='text' and col['length']>(2000 if col['source_type']=='CHAR' else 4000):
                issues.append({'code':'ORACLE_TEXT_LENGTH','table':table,'question':f'{table}.{name} needs a reviewed Oracle character/storage mapping.'})
    return issues

def ddl(schema: dict,database: str) -> str:
    """Emit complete DDL for a selected connection's current schema/default dataset."""
    if database not in {'sqlite','oracle','bigquery'}:raise Blocked('Unknown DDL target.','TARGET_CONFIG')
    q=lambda s:('`'+ident(s)+'`') if database=='bigquery' else ('"'+ident(s)+'"')
    output=[f'-- Target: {database}. Derived from source DDL, not from SQLite storage.']
    if database=='bigquery':output+=['-- Execute with a configured default dataset. NOT ENFORCED is a capability gap, not equivalence.']
    for table,spec in schema.items():
        parts=[]
        for name in spec['column_order']:
            col=spec['columns'][name];k=col['kind']
            if k=='integer':typ={'sqlite':'INTEGER','oracle':'NUMBER('+str(len(col['maximum']))+',0)','bigquery':'INT64'}[database]
            elif k=='decimal':
                p,s=col['precision'],col['scale'];bq='NUMERIC' if s<=9 and p-s<=29 else 'BIGNUMERIC'
                typ={'sqlite':'TEXT','oracle':f'NUMBER({p},{s})','bigquery':f'{bq}({p},{s})'}[database]
            else:
                n=col['length'];o=('CHAR' if col['source_type']=='CHAR' else 'VARCHAR2')+f'({n} CHAR)'
                typ={'sqlite':'TEXT','oracle':o,'bigquery':f'STRING({n})'}[database]
            value=q(name)+' '+typ+(' NOT NULL' if not col['nullable'] else '')
            if database!='bigquery':
                if k=='integer':value+=f' CHECK ({q(name)} BETWEEN {col["minimum"]} AND {col["maximum"]})'
                elif k=='text' and database=='sqlite':value+=f' CHECK (length({q(name)}) <= {col["length"]})'
            parts.append(value)
        if spec['primary_key']:parts.append('PRIMARY KEY ('+', '.join(q(x) for x in spec['primary_key'])+')'+(' NOT ENFORCED' if database=='bigquery' else ''))
        output.append('CREATE TABLE '+q(table)+' (\n  '+',\n  '.join(parts)+'\n);')
    return '\n\n'.join(output)+'\n'

def validate_value(col: dict,value):
    """Check lossless insert conversion before a database can round or coerce a value."""
    if value is None:
        if not col['nullable']:raise ValueError('NULL supplied to a non-null column.')
        return None
    if col['kind']=='text':
        if not isinstance(value,str):raise TypeError('Text columns require text, not a numeric conversion.')
        if len(value)>col['length']:raise ValueError('Text exceeds the source width.')
        return value.ljust(col['length']) if col['source_type']=='CHAR' else value
    if isinstance(value,(float,bool)):raise TypeError('Binary floats and booleans are not exact source numbers.')
    with localcontext() as dc:
        dc.prec=80;n=Decimal(value)
        if not n.is_finite():raise ValueError('Non-finite database number.')
        if col['kind']=='integer':
            if n!=n.to_integral_value() or not Decimal(col['minimum'])<=n<=Decimal(col['maximum']):raise ValueError('Integer violates source bounds or is fractional.')
            return int(n)
        s,p=col['scale'],col['precision'];quantum=Decimal(1).scaleb(-s)
        if n!=n.quantize(quantum) or abs(n)>=Decimal(10)**(p-s):raise ValueError('Decimal violates source precision/scale; no automatic rounding is allowed.')
        return format(n,f'.{s}f')
