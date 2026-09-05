"""Development-only independent fixture writer. NEVER use it to accept a migration.

The migration runner does not call this file. It does not import migration code.
Changing expected results to hide a failed comparison is prohibited.
"""
from pathlib import Path
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
CASES={
 'normal':[
  ('000003',100000,20260904,'N'),('000001',99999,20260904,'N'),
  ('000002',123456,20260903,'N'),('000002',250099,20260904,'N'),
  ('000005',200000,20260905,'N'),('000004',0,20270904,'X'),
  ('000006',75,20260904,'X'),('000007',123499,20260904,'N')],
 'boundaries':[
  ('000010',100000,20260904,'N'),('000011',99999,20260904,'N'),
  ('000012',99999999,20260904,'N'),('000013',1,20991231,'X'),
  ('000014',100001,20260905,'N'),('000015',100099,20260904,'N'),
  ('000015',100199,20260904,'N'),('000016',100000,20260903,'N'),
  ('000017',0,20260904,'N'),('000018',99999999,20991231,'X')],
 'empty':[]}

def encode(row):
    account,amount,date,kind=row
    return f'{account}{amount:08d}{date:08d}{kind}'.encode('cp037')

def main():
    manifest={}
    for name,rows in CASES.items():
        root=ROOT/'sample'/'cases'/name
        (root/'inputs').mkdir(parents=True,exist_ok=True)
        (root/'expected').mkdir(exist_ok=True)
        (root/'inputs'/'raw.bin').write_bytes(b''.join(encode(r) for r in rows))
        (root/'inputs'/'date.bin').write_bytes(b'20260904'.decode().encode('cp037'))
        accepted=[r for r in rows if r[3]=='X' or (r[1]>=100000 and r[2]<=20260904)]
        rejected=[r for r in rows if not(r[3]=='X' or (r[1]>=100000 and r[2]<=20260904))]
        ordered=sorted(accepted,key=lambda r:r[0].encode('cp037'))
        fees=[7 if r[3]=='X' else r[1]//100 for r in ordered]
        fee_bytes=b''.join(encode(r)+f'{fee:06d}'.encode('cp037') for r,fee in zip(ordered,fees))
        files={
          'accept.bin':b''.join(map(encode,accepted)),
          'reject.bin':b''.join(map(encode,rejected)),
          'sorted.bin':b''.join(map(encode,ordered)),
          'fees.bin':fee_bytes,'audit.bin':fee_bytes,
          'total.bin':f'{len(ordered):06d}{sum(r[1] for r in ordered):012d}{sum(fees):010d}'.encode('cp037')}
        for file,data in files.items():(root/'expected'/file).write_bytes(data)
        columns=['SEQ','ACCOUNT_ID','AMOUNT_CENTS','BUSINESS_DATE','CATEGORY','FEE_CENTS']
        dbrows=[[0,'999999',1,20260901,'Z',0]]+[[i,r[0],r[1],r[2],r[3],fee] for i,(r,fee) in enumerate(zip(ordered,fees),1)]
        (root/'expected'/'database.json').write_text(json.dumps({'ACCOUNT_LEDGER':{'columns':columns,'order_by':['SEQ'],'rows':dbrows}},indent=2)+'\n')
        (root/'initial.sql').write_text("INSERT INTO ACCOUNT_LEDGER (SEQ,ACCOUNT_ID,AMOUNT_CENTS,BUSINESS_DATE,CATEGORY,FEE_CENTS) VALUES (0,'999999',1,20260901,'Z',0);\n")
        for p in sorted(root.rglob('*')):
            if p.is_file():manifest[str(p.relative_to(ROOT/'sample')).replace('\\','/')]=hashlib.sha256(p.read_bytes()).hexdigest()
    (ROOT/'sample'/'baseline_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    dataset={
      'SAMPLE.RAW':('input','inputs/raw.bin',23),
      'SAMPLE.BDATE':('input','inputs/date.bin',8),
      'SAMPLE.ACCEPT':('intermediate','files/accept.bin',23),
      'SAMPLE.REJECT':('output','files/reject.bin',23),
      'SAMPLE.SORTED':('intermediate','files/sorted.bin',23),
      'SAMPLE.FEES':('output','files/fees.bin',29),
      'SAMPLE.AUDIT':('output','files/audit.bin',29),
      'SAMPLE.TOTAL':('output','files/total.bin',28)}
    config={
      'schema_version':1,'generation_mode':'offline_subset','process':'synthetic_accounts','repository':'repository',
      'inventory':'inventory.xlsx','sheet':'Process','source_format':'free',
      'collation':'cp037','execution_order':['JOB001','JOB002','JOB003','JOB004','JOB005'],
      'order_evidence':'Synthetic process specification; not an AutoSys export.',
      'ddl_sources':['ddl/ledger.sql'],'knowledge':'../knowledge/answers.json',
      'output':'../output','cache':'../.migration/cache','agent_artifacts':'../agent_artifacts',
      'timeout_seconds':30,'max_sort_records':100000,
      'baseline':{'kind':'synthetic','description':'Independent integer-cent specification; not mainframe execution.','manifest':'baseline_manifest.json'},
      'datasets':{k:{'role':r,'path':p,'format':'fixed','encoding':'cp037','record_length':n} for k,(r,p,n) in dataset.items()},
      'cases':[{'name':name,'path':'cases/'+name,'initial_database':'initial.sql',
        'return_codes':{j:0 for j in ['JOB001','JOB002','JOB003','JOB004','JOB005']},
        'expected_files':{dsn:'expected/'+Path(p).name for dsn,(role,p,n) in dataset.items() if role!='input'},
        'expected_database':'expected/database.json'} for name in CASES]}
    (ROOT/'sample'/'process.json').write_text(json.dumps(config,indent=2)+'\n')
if __name__=='__main__':main()
