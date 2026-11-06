"""Executable experiments for PostgreSQL versus Oracle AI Database for agent memory.

Only the fixed PG_ORACLE_* Oracle objects and postgres_oracle PostgreSQL schema are mutated.
No existing article tables, models, policies, or data are modified.
"""
import hashlib
import json
import math
import os
import platform
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import oracledb
import psycopg
from dotenv import load_dotenv

oracledb.defaults.program = 'devrel-developerhub-postgresql-versus-oracle-ai-database-for-agent-memory'
oracledb.defaults.fetch_lobs = False

from corpus import DOCS, QUERIES, CORPUS_VERSION, QRELS, validate_fixture

ROOT = Path(__file__).resolve().parent
EMBED_MODEL = 'ALL_MINILM_L12_V2'
RERANK_MODEL = 'BGE_RERANKER'
EMBED_MODEL_URL = ('https://objectstorage.us-ashburn-1.oraclecloud.com'
                   '/n/adwc4pm/b/OML-Resources/o/all_MiniLM_L12_v2.onnx')


def load_environment():
    """Find the nearest .env above this folder; preserve exported variables."""
    explicit = os.getenv('PG_ORACLE_ENV_FILE')
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise RuntimeError('PG_ORACLE_ENV_FILE must point to an existing .env file.')
    else:
        path = next((directory / '.env' for directory in (ROOT, *ROOT.parents)
                     if (directory / '.env').is_file()), None)
    if path is not None:
        load_dotenv(path, override=False)
    return path


def ndcg(ids, judgments, k=5):
    gains = [(2 ** judgments.get(i, 0) - 1) / math.log2(rank + 2)
             for rank, i in enumerate(ids[:k])]
    ideal = sum((2 ** g - 1) / math.log2(rank + 2)
                for rank, g in enumerate(sorted(judgments.values(), reverse=True)[:k]))
    return sum(gains) / ideal if ideal else 0.0


def recall(ids, judgments, k=8):
    relevant = {i for i, grade in judgments.items() if grade > 0}
    return len(set(ids[:k]) & relevant) / len(relevant) if relevant else 0.0


def vector_literal(v):
    return '[' + ','.join(format(float(x), '.9g') for x in v) + ']'


class MemoryLab:
    def __init__(self):
        load_environment()
        required = ['DB_USER', 'DB_PASSWORD', 'DB_DSN', 'PG_DSN']
        if any(not os.getenv(k) for k in required):
            raise RuntimeError('Add DB_USER, DB_PASSWORD, DB_DSN and PG_DSN to the repository-root .env; see README.md.')
        self.cfg = dict(user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], dsn=os.environ['DB_DSN'])
        self.o = oracledb.connect(**self.cfg)
        self.o.call_timeout = 300000
        try:
            self.p = psycopg.connect(os.environ['PG_DSN'], autocommit=True)
        except Exception:
            self.o.close()
            raise
        # Session-scoped lock survives transaction commits and releases on disconnect.
        if not self.p.execute('SELECT pg_try_advisory_lock(52671401)').fetchone()[0]:
            self.p.close()
            self.o.close()
            raise RuntimeError('This notebook already has an active database session. Run its cleanup cell or shut down its kernel before starting another run.')
        self.closed = False
        self.prefix = 'PG_ORACLE'
        self.mem = 'PG_ORACLE_MEMORY'
        self.edges = 'PG_ORACLE_EDGES'
        self.graph = 'PG_ORACLE_GRAPH'
        self.idx = 'PG_ORACLE_TEXT_IDX'
        self.policy_function = 'PG_ORACLE_TENANT_POLICY'
        self.schema = 'postgres_oracle'
        self.pg_role = 'postgres_oracle_reader'
        self.run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        self.created = []
        self.report = dict(started_at=datetime.now(timezone.utc).isoformat(),
                           python=platform.python_version(), oracle=self.o.version,
                           program=oracledb.defaults.program, checks={},
                           objects={'oracle_memory': self.mem, 'oracle_edges': self.edges,
                                    'oracle_graph': self.graph, 'postgres_memory': self.schema+'.memory'},
                           methodology={'documents': len(DOCS), 'queries': len(QUERIES),
                               'corpus_version': CORPUS_VERSION,
                               'eligible_active_acme': sum(d['tenant']=='acme' and d['active']==1 for d in DOCS),
                               'superseded_acme': sum(d['tenant']=='acme' and d['active']==0 for d in DOCS),
                               'other_tenant': sum(d['tenant']!='acme' for d in DOCS),
                               'candidate_depth_per_branch': 8, 'fused_candidate_depth': 8,
                               'evaluation_k': 5, 'rrf_constant': 60,
                               'vector_search': 'exact scans, no ANN indexes',
                               'embedding': EMBED_MODEL, 'reranker': RERANK_MODEL,
                               'postgres_inference': 'Oracle-generated vectors; same Oracle reranker scores applied externally in Python',
                               'rerank_api': 'DBMS_VECTOR_CHAIN.UTL_TO_RERANK provider=database',
                               'judgments': QRELS['assessment'],
                               'qrels_version': QRELS['version'],
                               'judged_pairs': sum(len(q['qrels']) for q in QUERIES),
                               'positive_pairs': sum(g > 0 for q in QUERIES for g in q['qrels'].values()),
                               'relevance_rubric': QRELS['rubric'],
                               'gain_function': '2**grade - 1',
                               'rank_discount': '1 / log2(rank + 1), rank starts at 1',
                               'ideal_ranking': 'all judged memories sorted by grade, truncated at k',
                               'recall_relevance_threshold': 1,
                               'aggregation': 'unweighted arithmetic mean across questions',
                               'not_tested': ['production relevance', 'latency or throughput', 'managed service performance', 'Deep Data Security IAM/JWT propagation', 'built-in hybrid vector index', 'Apache AGE']})
        self.report['postgres'] = self.p.execute('SHOW server_version').fetchone()[0]
        for name in ['corpus.py', 'qrels.json', 'lab.py', 'notebook_display.py']:
            self.report.setdefault('source_sha256', {})[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()

    def oq(self, sql, **binds):
        with self.o.cursor() as cur:
            cur.execute(sql, binds)
            return cur.fetchall() if cur.description else None

    def check(self, name, condition, **observed):
        self.report['checks'][name] = dict(passed=bool(condition), **observed)
        if not condition:
            raise AssertionError(name + ': ' + json.dumps(observed))
        return self.report['checks'][name]

    def models(self):
        metadata = {
          EMBED_MODEL: {'function':'embedding','embeddingOutput':'embedding','input':{'input':['DATA']}},
          RERANK_MODEL: {'function':'regression','regressionOutput':'output'}
        }
        for model, env in [(EMBED_MODEL, 'EMBEDDING_ONNX_FILE'), (RERANK_MODEL, 'RERANKER_ONNX_FILE')]:
            if not self.oq('SELECT model_name FROM user_mining_models WHERE model_name=:m', m=model):
                path = os.getenv(env)
                if path:
                    data = Path(path).expanduser().read_bytes()
                elif model == EMBED_MODEL:
                    with urllib.request.urlopen(EMBED_MODEL_URL, timeout=600) as response:
                        data = response.read()
                else:
                    raise RuntimeError(f'{model} is absent. Export the augmented BGE reranker and set {env}; see README.md.')
                self.report.setdefault('loaded_model_sha256', {})[model] = hashlib.sha256(data).hexdigest()
                with self.o.cursor() as cur:
                    blob = self.o.createlob(oracledb.DB_TYPE_BLOB)
                    timeout = self.o.call_timeout
                    self.o.call_timeout = 0
                    try:
                        blob.write(data)
                        cur.execute('BEGIN DBMS_VECTOR.LOAD_ONNX_MODEL(:n,:b,JSON(:m)); END;',
                                    n=model, b=blob, m=json.dumps(metadata[model]))
                    finally:
                        self.o.call_timeout = timeout
                        # The load can consume the temporary locator; LOB.close()
                        # is for explicitly opened LOBs, not freeing this buffer.
                        del blob
        dim = self.oq(f"SELECT VECTOR_DIMENSION_COUNT(VECTOR_EMBEDDING({EMBED_MODEL} USING 'agent memory' AS DATA)) FROM dual")[0][0]
        score = self.oq(f"SELECT PREDICTION({RERANK_MODEL} USING 'Who approves Cedar?' AS FIRST_INPUT, 'Priya approves Cedar releases.' AS SECOND_INPUT) FROM dual")[0][0]
        self.report['models'] = [dict(model=n, function=f, created=t.isoformat()) for n,f,t in self.oq(
            'SELECT model_name,mining_function,creation_date FROM user_mining_models WHERE model_name IN (:a,:b)',a=EMBED_MODEL,b=RERANK_MODEL)]
        return self.check('in_database_models', dim == 384 and math.isfinite(float(score)), dimensions=int(dim), rerank_logit=float(score))

    def database_rerank(self, query, documents):
        """Return local ONNX scores with zero-based positions, verified on this release."""
        if not documents:
            return []
        params = {'provider':'database', 'model':RERANK_MODEL,
                  'return_docs':True, 'top_n':len(documents)}
        value = self.oq("""SELECT JSON_SERIALIZE(
          DBMS_VECTOR_CHAIN.UTL_TO_RERANK(:q,JSON(:docs),JSON(:params))
          RETURNING CLOB) FROM dual""", q=query,
          docs=json.dumps({'documents':documents}), params=json.dumps(params))[0][0]
        return json.loads(value)

    def reset_objects(self):
        """Reset only this notebook's fixed objects, including interrupted setup."""
        if self.closed:
            raise RuntimeError('This experiment has been closed. Run the connection cell again.')
        self.o.rollback()
        self.p.execute('ROLLBACK')
        self.p.execute('RESET ROLE')
        # Explicit names, never prefix/wildcard deletion. Drop graph and edges first.
        objects = [('PROPERTY GRAPH', 'PG_ORACLE_GRAPH'),
                   ('TABLE', 'PG_ORACLE_EDGES'), ('TABLE', 'PG_ORACLE_MEMORY'),
                   ('TABLE', 'PG_ORACLE_TEXT_MANUAL'), ('TABLE', 'PG_ORACLE_TEXT_COMMIT'),
                   ('FUNCTION', 'PG_ORACLE_TENANT_POLICY')]
        for kind, name in objects:
            if self.oq('SELECT 1 FROM user_objects WHERE object_name=:n AND object_type=:t', n=name, t=kind):
                self.oq(f'DROP {kind} {name}' + (' PURGE' if kind == 'TABLE' else ''))
        self.p.execute('DROP SCHEMA IF EXISTS postgres_oracle CASCADE')
        self.p.execute('DROP ROLE IF EXISTS postgres_oracle_reader')
        self.created = []

    def setup(self):
        self.reset_objects()
        for key in ('retrieval', 'retrieval_summary', 'review_followups', 'deep_data_security'):
            self.report.pop(key, None)
        self.oq(f'''CREATE TABLE {self.mem} (
            id VARCHAR2(40) PRIMARY KEY, tenant_id VARCHAR2(30) NOT NULL,
            active NUMBER(1) NOT NULL, content VARCHAR2(2000) NOT NULL,
            embedding VECTOR(384,FLOAT32) NOT NULL)''')
        self.created.append(('TABLE', self.mem))
        self.oq(f'''CREATE TABLE {self.edges} (
            id VARCHAR2(40) PRIMARY KEY, tenant_id VARCHAR2(30) NOT NULL,
            src VARCHAR2(40) NOT NULL REFERENCES {self.mem}(id),
            dst VARCHAR2(40) NOT NULL REFERENCES {self.mem}(id))''')
        self.created.append(('TABLE', self.edges))
        self.oq(f'''CREATE PROPERTY GRAPH {self.graph}
          VERTEX TABLES ({self.mem} KEY(id) LABEL memory PROPERTIES(id,tenant_id,active))
          EDGE TABLES ({self.edges} KEY(id)
            SOURCE KEY(src) REFERENCES {self.mem}(id)
            DESTINATION KEY(dst) REFERENCES {self.mem}(id)
            LABEL cites PROPERTIES(id,tenant_id))''')
        self.created.append(('PROPERTY GRAPH', self.graph))
        # Explicit manual synchronization makes freshness behavior observable.
        self.oq(f"CREATE INDEX {self.idx} ON {self.mem}(content) INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (MANUAL)')")
        self.p.execute('CREATE EXTENSION IF NOT EXISTS vector')
        self.p.execute('CREATE EXTENSION IF NOT EXISTS pg_textsearch')
        self.p.execute(f'CREATE SCHEMA {self.schema}')
        self.p.execute(f'''CREATE TABLE {self.schema}.memory (
            id text PRIMARY KEY, tenant_id text NOT NULL, active integer NOT NULL,
            content text NOT NULL, embedding vector(384) NOT NULL)''')
        self.p.execute(f'''CREATE TABLE {self.schema}.edges (
            id text PRIMARY KEY, tenant_id text NOT NULL,
            src text NOT NULL REFERENCES {self.schema}.memory(id),
            dst text NOT NULL REFERENCES {self.schema}.memory(id))''')
        self.p.execute(f"CREATE INDEX memory_bm25 ON {self.schema}.memory USING bm25(content) WITH (text_config='english')")
        self.report['extensions'] = dict(self.p.execute("SELECT extname,extversion FROM pg_extension WHERE extname IN ('vector','pg_textsearch')").fetchall())
        return dict(oracle_objects=len(self.created), postgres_schema=self.schema, extensions=self.report['extensions'])

    def insert_oracle(self, id, text, tenant='acme', active=1):
        self.oq(f'''INSERT INTO {self.mem}(id,tenant_id,active,content,embedding)
            VALUES(:id,:t,:a,:c,VECTOR_EMBEDDING({EMBED_MODEL} USING :c AS DATA))''',id=id,t=tenant,a=active,c=text)

    def embed(self, text):
        return self.oq(f'SELECT VECTOR_EMBEDDING({EMBED_MODEL} USING :t AS DATA) FROM dual',t=text)[0][0]

    def seed(self):
        for d in DOCS:
            self.insert_oracle(d['id'],d['content'],d['tenant'],d['active'])
        self.oq(f"INSERT INTO {self.edges} VALUES('e01','acme','m01','m02')")
        self.o.commit()
        self.oq('BEGIN CTX_DDL.SYNC_INDEX(:i); END;',i=self.idx)
        rows = self.oq(f'SELECT id,tenant_id,active,content,embedding FROM {self.mem} ORDER BY id')
        with self.p.transaction():
            for id,tenant,active,content,vector in rows:
                self.p.execute(f'INSERT INTO {self.schema}.memory VALUES(%s,%s,%s,%s,%s::vector)',
                               (id,tenant,active,content,vector_literal(vector)))
            self.p.execute(f"INSERT INTO {self.schema}.edges VALUES('e01','acme','m01','m02')")
        return self.check('identical_seed_counts',len(rows)==len(DOCS)==self.p.execute(f'SELECT count(*) FROM {self.schema}.memory').fetchone()[0],documents=len(rows))

    def graph_rows(self, dst='m02'):
        return self.oq(f'''SELECT src_id,dst_id FROM GRAPH_TABLE ({self.graph}
          MATCH (a IS memory)-[e IS cites]->(b IS memory)
          WHERE a.tenant_id=:t AND b.tenant_id=:t AND e.tenant_id=:t AND b.id=:dst
          COLUMNS(a.id AS src_id,b.id AS dst_id))''',t='acme',dst=dst)

    def oracle_transactions(self):
        def write():
            self.insert_oracle('probe','freshnessprobe Cedar deployment approval')
            self.oq(f"INSERT INTO {self.edges} VALUES('ep','acme','m01','probe')")
        def counts(connection):
            with connection.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.mem} WHERE id='probe' AND embedding IS NOT NULL")
                a=cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM {self.edges} WHERE id='ep'")
                return [int(a),int(cur.fetchone()[0])]
        with oracledb.connect(**self.cfg) as observer:
            write()
            own=counts(self.o); unseen=counts(observer); own_graph=len(self.graph_rows('probe'))
            self.o.rollback()
            rolled=counts(observer)
            write(); self.o.commit()
            committed=counts(observer); committed_graph=len(self.graph_rows('probe'))
        before=self.oq(f"SELECT COUNT(*) FROM {self.mem} WHERE CONTAINS(content,'freshnessprobe',1)>0")[0][0]
        self.oq('BEGIN CTX_DDL.SYNC_INDEX(:i); END;',i=self.idx)
        after=self.oq(f"SELECT COUNT(*) FROM {self.mem} WHERE CONTAINS(content,'freshnessprobe',1)>0")[0][0]
        result=self.check('oracle_transaction_and_text_freshness',own==[1,1] and unseen==rolled==[0,0] and committed==[1,1] and own_graph==committed_graph==1 and before==0 and after==1,
                          own_uncommitted=own,other_uncommitted=unseen,after_rollback=rolled,after_commit=committed,graph_in_own_transaction=own_graph,graph_after_commit=committed_graph,text_before_sync=int(before),text_after_sync=int(after))
        self.oq(f"DELETE FROM {self.edges} WHERE id='ep'")
        self.oq(f"DELETE FROM {self.mem} WHERE id='probe'")
        self.o.commit();self.oq('BEGIN CTX_DDL.SYNC_INDEX(:i); END;',i=self.idx)
        self.oq("BEGIN CTX_DDL.OPTIMIZE_INDEX(:i,'FULL'); END;",i=self.idx)
        return result

    def pg_transactions(self):
        vec=vector_literal(self.embed('freshnessprobe Cedar deployment approval'))
        def write():
            self.p.execute(f"INSERT INTO {self.schema}.memory VALUES('probe','acme',1,%s,%s::vector)",('freshnessprobe Cedar deployment approval',vec))
            self.p.execute(f"INSERT INTO {self.schema}.edges VALUES('ep','acme','m01','probe')")
        def counts(c):
            return [c.execute(f"SELECT count(*) FROM {self.schema}.memory WHERE id='probe' AND embedding IS NOT NULL").fetchone()[0],c.execute(f"SELECT count(*) FROM {self.schema}.edges WHERE id='ep'").fetchone()[0]]
        with psycopg.connect(os.environ['PG_DSN'],autocommit=True) as observer:
            self.p.execute('BEGIN');write();own=counts(self.p);unseen=counts(observer)
            self.p.execute('ROLLBACK');rolled=counts(observer)
            with self.p.transaction(): write()
            committed=counts(observer)
            found=observer.execute(f"SELECT id FROM {self.schema}.memory WHERE content <@> to_bm25query('freshnessprobe',%s)<0 ORDER BY id",(f'{self.schema}.memory_bm25',)).fetchall()
        result=self.check('postgres_transaction_and_bm25_freshness',own==[1,1] and unseen==rolled==[0,0] and committed==[1,1] and found==[('probe',)],own_uncommitted=own,other_uncommitted=unseen,after_rollback=rolled,after_commit=committed,bm25_after_commit=len(found))
        with self.p.transaction():
            self.p.execute(f"DELETE FROM {self.schema}.edges WHERE id='ep'")
            self.p.execute(f"DELETE FROM {self.schema}.memory WHERE id='probe'")
        return result

    def retrieve_oracle(self, query, depth=8):
        if type(depth) is not int or not 1 <= depth <= 1000:
            raise ValueError("depth must be an integer between 1 and 1000")
        lex=' OR '.join(re.findall(r'[A-Za-z0-9]+',query['lexical']))
        vec=vector_literal(self.embed(query['text']))
        vsql=f'''SELECT id FROM {self.mem} WHERE tenant_id=:t AND active=1
          ORDER BY VECTOR_DISTANCE(embedding,TO_VECTOR(:v),COSINE),id FETCH FIRST {depth} ROWS ONLY'''
        lsql=f'''SELECT id FROM {self.mem} WHERE tenant_id=:t AND active=1 AND CONTAINS(content,:lex,1)>0
          ORDER BY SCORE(1) DESC,id FETCH FIRST {depth} ROWS ONLY'''
        vector=[r[0] for r in self.oq(vsql,t='acme',v=vec)]
        lexical=[r[0] for r in self.oq(lsql,t='acme',lex=lex)]
        # Rank fusion is computed in SQL. Each branch filters before candidate truncation.
        sql=f'''WITH v AS ({vsql}), l AS ({lsql}),
          vr AS (SELECT id,ROW_NUMBER() OVER(ORDER BY VECTOR_DISTANCE(embedding,TO_VECTOR(:v),COSINE),id) rn
                 FROM {self.mem} WHERE id IN (SELECT id FROM v)),
          lr AS (SELECT id,ROW_NUMBER() OVER(ORDER BY SCORE(2) DESC,id) rn
                 FROM {self.mem} WHERE id IN (SELECT id FROM l) AND CONTAINS(content,:lex,2)>0),
          scores AS (SELECT id,1.0/(60+rn) s FROM vr UNION ALL SELECT id,1.0/(60+rn) s FROM lr)
          SELECT id,SUM(s) FROM scores GROUP BY id ORDER BY SUM(s) DESC,id FETCH FIRST {depth} ROWS ONLY'''
        fused=[r[0] for r in self.oq(sql,t='acme',v=vec,lex=lex)]
        return dict(vector=vector,lexical=lexical,hybrid=fused),vec

    def retrieve_pg(self,query,vec,depth=8):
        if type(depth) is not int or not 1 <= depth <= 1000:
            raise ValueError("depth must be an integer between 1 and 1000")
        vsql=f'''SELECT id FROM {self.schema}.memory WHERE tenant_id=%(tenant)s AND active=1
          ORDER BY embedding <=> %(v)s::vector,id LIMIT {depth}'''
        lsql=f'''SELECT id FROM {self.schema}.memory WHERE tenant_id=%(tenant)s AND active=1
          AND content <@> to_bm25query(%(q)s,%(idx)s)<0
          ORDER BY content <@> to_bm25query(%(q)s,%(idx)s),id LIMIT {depth}'''
        b=dict(tenant='acme',v=vec,q=query['lexical'],idx=f'{self.schema}.memory_bm25')
        vector=[r[0] for r in self.p.execute(vsql,{k:b[k] for k in ['tenant','v']}).fetchall()]
        lexical=[r[0] for r in self.p.execute(lsql,{k:b[k] for k in ['tenant','q','idx']}).fetchall()]
        sql=f'''WITH v AS ({vsql}),l AS ({lsql}),
          vr AS (SELECT id,ROW_NUMBER() OVER(ORDER BY embedding <=> %(v)s::vector,id) rn
                 FROM {self.schema}.memory WHERE id IN (SELECT id FROM v)),
          lr AS (SELECT id,ROW_NUMBER() OVER(ORDER BY content <@> to_bm25query(%(q)s,%(idx)s),id) rn
                 FROM {self.schema}.memory WHERE id IN (SELECT id FROM l)),
          scores AS (SELECT id,1.0/(60+rn) s FROM vr UNION ALL SELECT id,1.0/(60+rn) s FROM lr)
          SELECT id,SUM(s) FROM scores GROUP BY id ORDER BY SUM(s) DESC,id LIMIT {depth}'''
        fused=[r[0] for r in self.p.execute(sql,b).fetchall()]
        return dict(vector=vector,lexical=lexical,hybrid=fused)

    def evaluate(self):
        validate_fixture()
        self.check('complete_qrels', all(len(q['qrels']) == len(DOCS) for q in QUERIES),
                   judged_pairs=sum(len(q['qrels']) for q in QUERIES),
                   positive_pairs=sum(g > 0 for q in QUERIES for g in q['qrels'].values()))
        details=[]
        self.check('ndcg_known_cases', ndcg(['a','b'],{'a':3,'b':1}) == 1.0
                   and ndcg(['x'],{'a':3}) == 0.0
                   and 0 < ndcg(['b','a'],{'a':3,'b':1}) < 1)
        eligible={d['id'] for d in DOCS if d['tenant']=='acme' and d['active']==1}
        for q in QUERIES:
            ora,vec=self.retrieve_oracle(q);pg=self.retrieve_pg(q,vec)
            # Both pipelines get the same cross-encoder. For PostgreSQL this is external inference.
            candidates=sorted(set(ora['hybrid'])|set(pg['hybrid']))
            binds={f'i{n}':id for n,id in enumerate(candidates)}
            clause=','.join(':'+k for k in binds)
            documents=self.oq(f'''SELECT id,content FROM {self.mem}
                 WHERE tenant_id='acme' AND active=1 AND id IN ({clause}) ORDER BY id''',**binds)
            ranked=self.database_rerank(q['text'],[text for _,text in documents])
            self.check(f'{q["id"]}_database_reranker_mapping',
                       len(ranked)==len(documents)
                       and {int(r['index']) for r in ranked}==set(range(len(documents)))
                       and all(r['content']==documents[int(r['index'])][1]
                               and math.isfinite(float(r['score'])) for r in ranked))
            scores={documents[int(r['index'])][0]:float(r['score']) for r in ranked}
            for system, ranks in [('oracle',ora),('postgres',pg)]:
                ranks['hybrid_rerank']=sorted(ranks['hybrid'],key=lambda id:(-scores[id],id))
                for method, ids in ranks.items():
                    self.check(f'{q["id"]}_{system}_{method}_scope',set(ids)<=eligible,returned=len(ids))
                    details.append(dict(query=q['id'],system=system,method=method,ids=ids,
                                        ndcg_at_5=ndcg(ids,q['qrels']),recall_at_8=recall(ids,q['qrels'])))
            self.check(f'{q["id"]}_identical_exact_vector_order',ora['vector']==pg['vector'])
            print(q['id'], 'complete', flush=True)
        summary=[]
        for system in ['oracle','postgres']:
            for method in ['vector','lexical','hybrid','hybrid_rerank']:
                rows=[r for r in details if r['system']==system and r['method']==method]
                summary.append(dict(system=system,method=method,
                    mean_ndcg_at_5=sum(r['ndcg_at_5'] for r in rows)/len(rows),
                    mean_recall_at_8=sum(r['recall_at_8'] for r in rows)/len(rows)))
        self.report.update(retrieval=details,retrieval_summary=summary)
        return summary

    def scope_and_security(self):
        # Fixed-tenant policies isolate this test from authentication and session-context setup.
        # They demonstrate database enforcement, NOT identity propagation or Deep Data Security.
        self.oq("SELECT privilege FROM session_privs WHERE privilege='EXEMPT ACCESS POLICY'")
        if self.oq("SELECT privilege FROM session_privs WHERE privilege='EXEMPT ACCESS POLICY'") or self.o.username.upper()=='SYS':
            raise RuntimeError('VPD verification requires a non-SYS account without EXEMPT ACCESS POLICY.')
        func=self.policy_function
        self.oq(f"""CREATE FUNCTION {func}(s VARCHAR2,t VARCHAR2) RETURN VARCHAR2 AS
            BEGIN RETURN 'tenant_id = ''acme'''; END;""")
        self.created.append(('FUNCTION',func))
        self.oq('''BEGIN DBMS_RLS.ADD_POLICY(object_schema=>USER,object_name=>:t,
          policy_name=>'pgo_scope',policy_function=>:f,statement_types=>'SELECT'); END;''',t=self.mem,f=func)
        visible=self.oq(f'SELECT DISTINCT tenant_id FROM {self.mem}')
        forbidden=self.oq(f"SELECT COUNT(*) FROM {self.mem} WHERE tenant_id='other'")[0][0]
        orlex=self.oq(f"SELECT DISTINCT tenant_id FROM {self.mem} WHERE CONTAINS(content,'Cedar',1)>0")
        role=self.schema+'_reader'
        self.pg_role=role
        self.p.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
        self.p.execute(f'GRANT USAGE ON SCHEMA {self.schema} TO {role}')
        self.p.execute(f'GRANT SELECT ON {self.schema}.memory TO {role}')
        self.p.execute(f'ALTER TABLE {self.schema}.memory ENABLE ROW LEVEL SECURITY')
        self.p.execute(f"CREATE POLICY tenant_scope ON {self.schema}.memory FOR SELECT TO {role} USING(tenant_id='acme')")
        try:
            self.p.execute(f'SET ROLE {role}')
            pgvisible=self.p.execute(f'SELECT DISTINCT tenant_id FROM {self.schema}.memory').fetchall()
            pgforbidden=self.p.execute(f"SELECT COUNT(*) FROM {self.schema}.memory WHERE tenant_id='other'").fetchone()[0]
            pglex=self.p.execute(f"SELECT DISTINCT tenant_id FROM {self.schema}.memory WHERE content <@> to_bm25query('Cedar',%s)<0",(f'{self.schema}.memory_bm25',)).fetchall()
        finally:
            self.p.execute('RESET ROLE')
        return self.check('database_row_policies',visible==pgvisible==orlex==pglex==[('acme',)] and forbidden==pgforbidden==0,
                          oracle_other_rows=int(forbidden),postgres_other_rows=pgforbidden,
                          identity_model='fixed acme predicate; not an end-user authentication test')

    def save(self, name=None):
        name = name or f'run-{self.run_id}.json'
        self.report['finished_at']=datetime.now(timezone.utc).isoformat()
        self.report['passed_checks']=sum(v['passed'] for v in self.report['checks'].values())
        self.report['failed_checks']=sum(not v['passed'] for v in self.report['checks'].values())
        (ROOT/'results').mkdir(exist_ok=True)
        path=ROOT/'results'/name
        path.write_text(json.dumps(self.report,indent=2)+'\n')
        return {'result':str(path.name),'passed':self.report['passed_checks'],'failed':self.report['failed_checks']}

    def cleanup(self):
        if self.closed:
            return {'run_objects_removed': True, 'existing_models_preserved': True}
        try:
            self.reset_objects()
        finally:
            self.o.close()
            self.p.close()  # Releases the notebook's session advisory lock.
            self.closed = True
        return {'run_objects_removed': True, 'existing_models_preserved': True}


def run():
    lab=MemoryLab()
    try:
        print(lab.models());print(lab.setup());print(lab.seed())
        print(lab.check('sql_property_graph',lab.graph_rows()==[('m01','m02')]))
        print(lab.oracle_transactions());print(lab.pg_transactions())
        print(json.dumps(lab.evaluate(),indent=2));print(lab.scope_and_security())
        print(lab.save())
    finally:
        print(lab.cleanup())

if __name__=='__main__':
    run()
