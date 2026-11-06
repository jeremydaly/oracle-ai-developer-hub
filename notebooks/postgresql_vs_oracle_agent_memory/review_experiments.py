"""Candidate-depth evaluation, raw query embedding, and Oracle Text."""
import hashlib
import math
from pathlib import Path
import oracledb
oracledb.defaults.program = 'devrel-developerhub-postgresql-versus-oracle-ai-database-for-agent-memory'
from corpus import DOCS, QUERIES
from lab import EMBED_MODEL, ndcg, recall


def evaluate_ten(lab):
    details=[]
    eligible={d['id'] for d in DOCS if d['tenant']=='acme' and d['active']==1}
    for q in QUERIES:
        ora,vec=lab.retrieve_oracle(q,depth=10)
        pg=lab.retrieve_pg(q,vec,depth=10)
        candidates=sorted(set(ora['hybrid']) | set(pg['hybrid']))
        texts={d['id']:d['content'] for d in DOCS}
        documents=[texts[i] for i in candidates]
        ranked=lab.database_rerank(q['text'],documents)
        lab.check(q['id']+'_depth10_reranker_mapping',
            len(ranked)==len(documents)
            and {int(r['index']) for r in ranked}==set(range(len(documents)))
            and all(r['content']==documents[int(r['index'])] and math.isfinite(float(r['score'])) for r in ranked))
        scores={candidates[int(r['index'])]:float(r['score']) for r in ranked}
        for system,ranks in [('oracle',ora),('postgres',pg)]:
            ranks['hybrid_rerank']=sorted(ranks['hybrid'],key=lambda i:(-scores[i],i))
            lab.check(q['id']+'_'+system+'_depth10_scope',all(set(ids)<=eligible and len(ids)<=10 for ids in ranks.values()))
            for method,ids in ranks.items():
                details.append(dict(query=q['id'],system=system,method=method,ids=ids,
                    ndcg_at_5=ndcg(ids,q['qrels'],5),ndcg_at_10=ndcg(ids,q['qrels'],10),recall_at_10=recall(ids,q['qrels'],10)))
    summary=[]
    for system in ['oracle','postgres']:
        for method in ['vector','lexical','hybrid','hybrid_rerank']:
            rows=[r for r in details if r['system']==system and r['method']==method]
            summary.append(dict(system=system,method=method,**{f'mean_{m}':sum(r[m] for r in rows)/len(rows) for m in ['ndcg_at_5','ndcg_at_10','recall_at_10']}))
    return dict(candidate_depth=10,fused_depth=10,rrf_constant=60,summary=summary,queries=details,
        interpretation='The depth-eight and depth-ten evaluations use the same 100 memories, eight questions, complete qrels, models, filters, and lexical queries. Editorial relevance judgments are fixed for this run. No held-out set or independent validation.')


def inline_query_embedding(lab):
    q=QUERIES[0]
    expected=lab.retrieve_oracle(q,depth=10)[0]['vector']
    sql=f'''SELECT id FROM {lab.mem}
        WHERE tenant_id=:tenant AND active=1
        ORDER BY VECTOR_DISTANCE(embedding,
          VECTOR_EMBEDDING({EMBED_MODEL} USING :query_text AS DATA),COSINE),id
        FETCH FIRST 10 ROWS ONLY'''
    actual=[r[0] for r in lab.oq(sql,tenant='acme',query_text=q['text'])]
    lab.check('inline_raw_query_embedding',actual==expected,ids=actual)
    return dict(sql=sql,ids=actual)


def text_features(lab):
    tables=[]
    result={}
    try:
        for mode in ['MANUAL','ON COMMIT']:
            suffix='N' if mode=='MANUAL' else 'C'
            table='PG_ORACLE_TEXT_MANUAL' if mode=='MANUAL' else 'PG_ORACLE_TEXT_COMMIT'
            index=table+'_IDX'
            lab.oq(f'CREATE TABLE {table}(id VARCHAR2(20) PRIMARY KEY,content VARCHAR2(1000))')
            tables.append(table)
            lab.oq(f"CREATE INDEX {index} ON {table}(content) INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS('MAINTENANCE MANUAL SYNC ({mode})')")
            docs=[('adjacent','connection pooling reduces session setup costs.'),
                  ('nearby','connection reuse makes pooling efficient.'),
                  ('far','connection reuse across many separate services requires careful configuration before enabling pooling.'),
                  ('other','session caching reduces setup costs.')]
            for id,text in docs:
                lab.oq(f'INSERT INTO {table} VALUES(:i,:t)',i=id,t=text)
            with oracledb.connect(**lab.cfg) as observer:
                def count():
                    with observer.cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE CONTAINS(content,'connection',1)>0")
                        return cur.fetchone()[0]
                before=count()
                lab.o.commit()
                committed=count()
                if mode=='MANUAL': lab.oq('BEGIN CTX_DDL.SYNC_INDEX(:i); END;',i=index)
                synchronized=count()
                lab.oq(f"INSERT INTO {table} VALUES('rollback','rollbackprobe connection pooling')")
                lab.o.rollback()
                with observer.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE CONTAINS(content,'rollbackprobe',1)>0")
                    rolled=cur.fetchone()[0]
            lab.check('text_'+suffix+'_freshness',before==0 and committed==(0 if mode=='MANUAL' else 3) and synchronized==3 and rolled==0,
                before_commit=int(before),after_commit=int(committed),after_sync=int(synchronized),rolled_back_matches=int(rolled))
            near_sql=f"SELECT id,content,SCORE(1) FROM {table} WHERE CONTAINS(content,'NEAR((connection, pooling), 5)',1)>0 ORDER BY SCORE(1) DESC,id"
            near=lab.oq(near_sql)
            both=lab.oq(f"SELECT id FROM {table} WHERE CONTAINS(content,'connection AND pooling',1)>0 ORDER BY id")
            lab.check('text_'+suffix+'_near',set(r[0] for r in near)=={'adjacent','nearby'} and len(both)==3,
                near_ids=[r[0] for r in near],and_ids=[r[0] for r in both])
            result[mode]=dict(near_sql=near_sql,near_rows=near,and_ids=[r[0] for r in both],after_commit=int(committed),after_sync=int(synchronized))
        return result
    finally:
        lab.o.rollback()
        for table in reversed(tables): lab.oq(f'DROP TABLE {table} PURGE')


def run_review_experiments(lab):
    lab.report.setdefault('source_sha256',{})['review_experiments.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result=dict(retrieval_depth10=evaluate_ten(lab),raw_query=inline_query_embedding(lab),oracle_text=text_features(lab))
    lab.report['review_followups']=result
    return result
