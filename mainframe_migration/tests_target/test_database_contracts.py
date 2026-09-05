"""Driver/REST contract probes. Fake transport tests are NOT live DB tests."""
from pathlib import Path
from decimal import Decimal
from types import ModuleType
from unittest.mock import patch
import json,tempfile,unittest
from migration.targets.schema import parse_schema,capabilities
from migration.targets.config import load_target
ROOT=Path(__file__).resolve().parents[1]
SOURCE='CREATE TABLE T (I BIGINT NOT NULL, C CHAR(6) NOT NULL, D DECIMAL(31,12));'
class DatabaseContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.schema=parse_schema(SOURCE)
    def tearDown(self):self.tmp.cleanup()
    def adapter(self,database,mode='contract'):
        text=(ROOT/'migration/targets/templates/python/database.py.txt').read_text().replace('@@DATABASE@@',database)
        module=ModuleType('tested_'+database);exec(compile(text,'generated_adapter.py','exec'),module.__dict__)
        payload={'database':database,'schema':self.schema,'execution_mode':mode,'work_root':str(self.root),
                 'capability_blockers':[],'allow_remote':True,'connections':load_target(ROOT/'target.json')['connections']}
        return module,module.Database(payload)
    def test_high_precision_value_is_not_routed_through_float(self):
        m,db=self.adapter('oracle');db.insert('T',['I','C','D'],[9223372036854775807,'000001',Decimal('1234567890123456789.123456789012')])
        self.assertEqual(db.operations[0]['values'][2],'1234567890123456789.123456789012')
        self.assertEqual(db.operations[0]['values'][0],9223372036854775807)
    def test_binary_float_and_overflow_are_rejected(self):
        m,db=self.adapter('sqlite')
        for bad in (1.1,Decimal('9223372036854775808')):
            with self.assertRaises((ValueError,TypeError)):db.insert('T',['I','C','D'],[bad,'000001',None])
    def test_uncommitted_transaction_is_not_repaired_with_commit(self):
        m,db=self.adapter('sqlite');db.insert('T',['I','C','D'],[1,'000001',None])
        with self.assertRaises(ValueError):db.finish()
        self.assertNotIn('commit',[x['op'] for x in db.operations]);self.assertEqual(db.operations[-1]['op'],'rollback')
    def test_context_database_must_equal_generated_database(self):
        m,db=self.adapter('oracle');payload=dict(db.payload);payload['database']='sqlite'
        with self.assertRaises(ValueError):m.Database(payload)
    def test_bigquery_session_binding_and_commit_are_explicit(self):
        m,db=self.adapter('bigquery','native');sent=[]
        def wire(method,url,body=None):
            sent.append(body)
            return {'status':{'state':'DONE'},'statistics':{'sessionInfo':{'sessionId':'synthetic-session'}}}
        db._wire=wire
        env={'MIGRATION_BQ_PROJECT':'test-project','MIGRATION_BQ_DATASET':'test_dataset','MIGRATION_BQ_LOCATION':'US'}
        with patch.dict(m.os.environ,env):
            db.insert('T',['I','C','D'],[1,'000001',Decimal('1234567890123456789.123456789012')]);db.commit()
        queries=[x['configuration']['query'] for x in sent]
        self.assertEqual(len(queries),3)
        self.assertTrue(queries[0]['createSession'])
        self.assertEqual(queries[1]['connectionProperties'],[{'key':'session_id','value':'synthetic-session'}])
        self.assertEqual(queries[1]['queryParameters'][2]['parameterType']['type'],'BIGNUMERIC')
        self.assertEqual(queries[1]['queryParameters'][2]['parameterValue']['value'],'1234567890123456789.123456789012')
        self.assertEqual(queries[2]['query'],'COMMIT TRANSACTION;')
        self.assertEqual(len((self.root/'remote_job_ids.jsonl').read_text().splitlines()),3)
    def test_ambiguous_remote_outcome_is_not_retried_or_called_successful(self):
        m,db=self.adapter('bigquery','native');attempts=[]
        def wire(*args):attempts.append(args);raise TimeoutError('synthetic unknown response')
        db._wire=wire
        with patch.dict(m.os.environ,{'MIGRATION_BQ_PROJECT':'p','MIGRATION_BQ_DATASET':'d','MIGRATION_BQ_LOCATION':'US'}):
            with self.assertRaises(TimeoutError):db.insert('T',['I','C','D'],[1,'000001',None])
            db.close()
        self.assertTrue(db.uncertain);self.assertEqual(len(attempts),1)
    def test_invalid_bigquery_dataset_is_blocked_before_transport(self):
        m,db=self.adapter('bigquery','native');calls=[]
        db._wire=lambda *a: calls.append(a) or {'status':{'state':'DONE'},'statistics':{'sessionInfo':{'sessionId':'s'}}}
        with patch.dict(m.os.environ,{'MIGRATION_BQ_PROJECT':'p','MIGRATION_BQ_DATASET':'bad-dataset','MIGRATION_BQ_LOCATION':'US'}):
            with self.assertRaises(ValueError):db.insert('T',['I','C','D'],[1,'000001',None])
        self.assertEqual(calls,[])
    def test_oracle_binding_does_not_build_values_into_sql(self):
        m,db=self.adapter('oracle','native');calls=[]
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def execute(self,sql,values):calls.append((sql,values))
        class Conn:
            def cursor(self):return Cursor()
        db.conn=Conn();db.insert('T',['I','C','D'],[1,"A'B",Decimal('123.000000000001')])
        self.assertIn(':p0',calls[0][0]);self.assertNotIn("A'B",calls[0][0]);self.assertEqual(calls[0][1][1],"A'B   ")
        self.assertIsInstance(calls[0][1][2],Decimal)
if __name__=='__main__':unittest.main()
