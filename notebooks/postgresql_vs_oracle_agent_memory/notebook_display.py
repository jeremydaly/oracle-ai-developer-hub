"""Readable, static notebook outputs; no database access or metric changes."""
import inspect
import hashlib
import json
from pathlib import Path
import math
import textwrap
from html import escape
from IPython.display import Code, HTML, Markdown, display
from corpus import DOCS, QUERIES, QRELS

ENGINES = {'oracle': 'Oracle', 'postgres': 'PostgreSQL'}
METHODS = {'vector': 'Dense vectors', 'lexical': 'Lexical search',
           'hybrid': 'Vector + lexical (RRF)', 'hybrid_rerank': 'RRF + BGE reranking'}
GRADES = {0: '0 · Irrelevant', 1: '1 · Qualification', 2: '2 · Support', 3: '3 · Direct answer'}
TEXTS = {d['id']: d['content'] for d in DOCS}


def retrieval_results(depth, report=None):
    """Read current-kernel results or the included reference, without connecting."""
    if depth not in (8, 10):
        raise ValueError('Choose candidate depth 8 or 10.')
    root = Path(__file__).resolve().parent
    if report is None:
        path = root / 'results' / 'verification.json'
        if not path.is_file():
            raise FileNotFoundError('The included results/verification.json is missing. Restore it or run the notebook in order.')
        report = json.loads(path.read_text())
        origin = 'included reference: results/verification.json'
    else:
        origin = 'current kernel experiment'
    for name in ('corpus.py', 'qrels.json'):
        expected = report.get('source_sha256', {}).get(name)
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if expected != actual:
            raise ValueError(f'Results do not match the current {name}. Rerun the experiment before inspecting these rankings.')
    if depth == 8:
        rows = report.get('retrieval')
    else:
        rows = report.get('review_followups', {}).get('retrieval_depth10', {}).get('queries')
    if not rows:
        raise ValueError(f'The current report has no depth-{depth} results. Run its evaluation cell first, '
                         'or pass report=None to inspect the included reference.')
    display(Markdown(f"**Results source:** {origin}. Run started: {report.get('started_at', 'unknown')}. "
                     'This cell reads recorded rankings; it does not connect to either database.'))
    return rows


def table(title, columns, rows, caption=None):
    """Escape cell content; keep long text wrapped and narrow screens scrollable."""
    head = ''.join(f'<th scope="col" style="text-align:left;vertical-align:top">{escape(str(c))}</th>' for c in columns)
    body = ''.join('<tr>' + ''.join(f'<td style="text-align:left;vertical-align:top;white-space:normal">{escape(str(c))}</td>' for c in row) + '</tr>' for row in rows)
    note = f'<p>{escape(caption)}</p>' if caption else ''
    weights = [55 if c in ('Memory text', 'Question', 'Observation') else 35 if c == 'Reason'
               else 15 if c in ('Grade', 'nDCG@5 contribution') else 10 for c in columns]
    cols = '<colgroup>' + ''.join(f'<col style="width:{100*w/sum(weights):.2f}%">' for w in weights) + '</colgroup>'
    display(HTML(f'''<section class="memory-report"><style>
    .memory-report table {{border-collapse:collapse; width:100%; font-size:0.95em;}}
    .memory-report th,.memory-report td {{text-align:left; vertical-align:top; padding:9px 12px;
      border-bottom:1px solid #8886; white-space:normal; overflow-wrap:anywhere;}}
    .memory-report th {{font-weight:600; border-bottom:2px solid #8888;}}
    .memory-report tbody tr:nth-child(even) {{background:rgba(128,128,128,.06);}}
    .memory-report h3 {{margin:1.1em 0 .5em;}}
    </style><h3>{escape(title)}</h3>{note}<div style="overflow-x:auto">
    <table style="table-layout:fixed">{cols}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></section>'''))


def highlighted(text, language):
    html = Code(text, language=language)._repr_html_()
    return html.replace('<pre>', '<pre style="font-family:ui-monospace,SFMono-Regular,Consolas,monospace;'
                        'font-size:13px;line-height:1.5;white-space:pre;overflow-x:auto;padding:12px;'
                        'background:#f7f7f7;color:#222;border:1px solid #ddd">')


def source(function, purpose):
    """Keep implementation inspectable without interrupting the result walkthrough."""
    code = highlighted(textwrap.dedent(inspect.getsource(function)), 'python')
    display(HTML(f'<details><summary><strong>View Python: {escape(function.__name__)}</strong> '
                 f'— {escape(purpose)}</summary>{code}</details>'))


def sql(text, title):
    display(Markdown(f'### {title}'))
    display(HTML(highlighted(textwrap.dedent(text).strip(), 'sql')))


def check_summary(lab, names=None, title='Checks'):
    checks = lab.report['checks']
    selected = names if names is not None else list(checks)
    table(title, ['Check', 'Result'],
          [(name.replace('_', ' '), 'PASS' if checks[name]['passed'] else 'FAIL') for name in selected])


def fixture(query_id='q1'):
    table('Corpus and judgment coverage', ['Memories', 'Eligible', 'Questions', 'Judged pairs', 'Positive pairs'],
          [(len(DOCS), sum(d['tenant']=='acme' and d['active']==1 for d in DOCS), len(QUERIES),
            sum(len(q['qrels']) for q in QUERIES), sum(g>0 for q in QUERIES for g in q['qrels'].values()))])
    table('Question index', ['ID', 'Question', 'Relevant memories'],
          [(q['id'], q['text'], sum(g>0 for g in q['qrels'].values())) for q in QUERIES])
    q = next(q for q in QUERIES if q['id']==query_id)
    table(f"Judgments for {query_id}: {q['text']}", ['Memory', 'Grade', 'Memory text', 'Reason'],
          [(i, GRADES[j['grade']], TEXTS[i], j['reason']) for i,j in QRELS['judgments'][query_id].items() if j['grade']>0],
          'These are the expected useful memories, defined before retrieval. All zero judgments are in qrels.json.')


def scores(rows, depth=8):
    metrics = [('mean_ndcg_at_5','Mean nDCG@5')]
    if depth==10: metrics.append(('mean_ndcg_at_10','Mean nDCG@10'))
    metrics.append((f'mean_recall_at_{depth}', f'Mean Recall@{depth}'))
    table(f'Retrieval quality with {depth} candidates', ['Engine', 'Method']+[label for _,label in metrics],
          [(ENGINES[r['system']], METHODS[r['method']])+tuple(f'{r[key]:.4f}' for key,_ in metrics) for r in rows],
          'Each value is an equally weighted average across eight questions. Higher is better; 1.0 is the maximum.')


def missing(query, ids):
    absent = [(i,g) for i,g in query['qrels'].items() if g>0 and i not in ids]
    if absent:
        table('Relevant memories missing from this candidate list', ['Memory', 'Grade', 'Memory text'],
              [(i,GRADES[g],TEXTS[i]) for i,g in absent],
              'These records reduce recall. Reranking this list cannot recover a memory that is absent from it.')
    else:
        display(Markdown('**No relevant memories are missing from this candidate list.**'))


def ranking(details, query_id='q6', engine='oracle', method='hybrid'):
    q = next(q for q in QUERIES if q['id']==query_id)
    matches = [r for r in details if r['query']==query_id]
    table(f"{query_id}: {q['text']}", ['Engine', 'Method', 'nDCG@5', 'Recall@8'],
          [(ENGINES[r['system']],METHODS[r['method']],f"{r['ndcg_at_5']:.4f}",f"{r['recall_at_8']:.4f}") for r in matches],
          'This table compares methods for one question. The detailed list below shows only your selected engine and method.')
    row = next(r for r in matches if r['system']==engine and r['method']==method)
    ideal = sum((2**g-1)/math.log2(rank+1) for rank,g in enumerate(sorted(q['qrels'].values(),reverse=True)[:5],1))
    records=[]
    for rank,i in enumerate(row['ids'],1):
        grade=q['qrels'][i]
        contribution = f'{(2**grade-1)/math.log2(rank+1)/ideal:.4f}' if rank<=5 else 'Outside top 5'
        records.append((rank,i,GRADES[grade],contribution,TEXTS[i]))
    table(f'{ENGINES[engine]} · {METHODS[method]} · returned order',
          ['Rank','Memory','Grade','nDCG@5 contribution','Memory text'],records,
          'The first five contributions sum to nDCG@5 (before rounding). All eight positions can contribute to Recall@8.')
    hits=sum(q['qrels'][i]>0 for i in row['ids']);total=sum(g>0 for g in q['qrels'].values())
    display(Markdown(f'**Reading this result:** {hits} of {total} relevant memories appear in the list '
                     f'(Recall@8 = {row["recall_at_8"]:.3f}). A grade-3 answer below grade-0 or grade-1 text '
                     'is an ordering problem that nDCG penalizes. Coverage details appear below.'))
    missing(q,row['ids'])


def reranking(details, query_id='q7', engine='oracle'):
    records=[]
    for q in QUERIES:
        for e in ENGINES:
            rows={r['method']:r for r in details if r['query']==q['id'] and r['system']==e}
            a,b=rows['hybrid'],rows['hybrid_rerank']
            records.append((q['id'],ENGINES[e],f"{a['ndcg_at_10']:.4f}",f"{b['ndcg_at_10']:.4f}",
                            f"{b['ndcg_at_10']-a['ndcg_at_10']:+.4f}",f"{a['recall_at_10']:.3f}"))
    table('RRF before and after BGE reranking',
          ['Query','Engine','RRF nDCG@10','BGE nDCG@10','Change','Recall@10'],records,
          'Positive change means better ordering under the qrels; negative change means worse. Reranking keeps the same candidate set, so recall is unchanged.')
    q=next(q for q in QUERIES if q['id']==query_id)
    rows={r['method']:r for r in details if r['query']==query_id and r['system']==engine}
    before,after=rows['hybrid'],rows['hybrid_rerank']
    ranks={i:rank for rank,i in enumerate(before['ids'],1)}
    records=[]
    for rank,i in enumerate(after['ids'],1):
        change=ranks[i]-rank
        movement=f'Up {change}' if change>0 else f'Down {-change}' if change<0 else 'Same'
        records.append((i,GRADES[q['qrels'][i]],ranks[i],rank,movement,TEXTS[i]))
    table(f"{query_id}: {q['text']} · {ENGINES[engine]}",
          ['Memory','Grade','RRF rank','BGE rank','Movement','Memory text'],records,
          'Rows are in BGE order. Check whether high-grade answers move up and low-grade or irrelevant records move down.')
    delta=after['ndcg_at_10']-before['ndcg_at_10']
    display(Markdown(f'**Reading this result:** nDCG@10 changes from {before["ndcg_at_10"]:.4f} '
                     f'to {after["ndcg_at_10"]:.4f} ({delta:+.4f}). '
                     f'Recall@10 stays at {before["recall_at_10"]:.3f}. '
                     'Relevance grades come from qrels.json; they are not BGE model scores.'))
    missing(q,before['ids'])


def transactions(lab,engine):
    key='oracle_transaction_and_text_freshness' if engine=='oracle' else 'postgres_transaction_and_bm25_freshness'
    c=lab.report['checks'][key]
    table(f'{ENGINES[engine]} transaction visibility', ['Observation','Memory rows','Edge rows'],
          [('Writing connection before commit',*c['own_uncommitted']),
           ('Independent connection before commit',*c['other_uncommitted']),
           ('After rollback',*c['after_rollback']),('After commit',*c['after_commit'])],
          'Each count refers to the temporary probe written by this experiment. Memory and provenance become visible together at commit.')
    if engine=='oracle':
        table('Oracle Text visibility', ['Before explicit sync','After explicit sync'],
              [(c['text_before_sync'],c['text_after_sync'])],
              'The probe is committed, but this manually synchronized text index needs an explicit sync before it finds the text.')
    else:
        table('PostgreSQL BM25 visibility', ['Matches after commit'],[(c['bm25_after_commit'],)],
              'The configured pg_textsearch index finds the committed probe immediately.')
    check_summary(lab,[key])


def text_probes(lab,followups):
    sql(followups['raw_query']['sql'],'Query embedding inside the executed SQL')
    display(Markdown('The raw-text query returned the same ordered memory IDs as the separately embedded query. '
                     'The check verifies equivalent results for this question.'))
    table('Oracle Text synchronization', ['Mode','Before commit','After commit','After explicit sync','Rolled-back probe'],
          [(mode,lab.report['checks']['text_'+suffix+'_freshness']['before_commit'],
            lab.report['checks']['text_'+suffix+'_freshness']['after_commit'],
            lab.report['checks']['text_'+suffix+'_freshness']['after_sync'],
            lab.report['checks']['text_'+suffix+'_freshness']['rolled_back_matches'])
           for mode,suffix in [('MANUAL','N'),('ON COMMIT','C')]],
          'Values are matching document counts observed from another connection. ON COMMIT makes the text searchable at commit; MANUAL requires explicit synchronization.')
    probe=followups['oracle_text']['ON COMMIT']
    sql(probe['near_sql'],'The executed proximity query')
    table('Term proximity', ['Query','Matching fixture IDs'],
          [('connection AND pooling',', '.join(probe['and_ids'])),
           ('NEAR((connection, pooling), 5)',', '.join(r[0] for r in probe['near_rows']))],
          'NEAR excludes the far-apart occurrence while keeping both nearby examples. This tests a filter, not a ranking-quality improvement.')


def dds_results(lab,dds):
    if dds.get('status')=='not_run':
        display(Markdown('**DDS was not run.** '+dds['reason']));return
    records=[]
    for role,observation in dds['observations'].items():
        for memory_id,tenant,content,amount in observation['rows']:
            records.append((role.capitalize(),memory_id,tenant,content,'NULL (masked)' if amount is None else amount))
    table('The same SELECT under different end-user identities',
          ['Role','Row','Tenant','Case','Payment amount'],records,
          'Both roles see the Acme cases and no other-tenant case. Support sees a masked amount on the finance-owned case; Finance sees both amounts.')
    sql(next(iter(dds['observations'].values()))['sql'],'The SELECT used by both roles')
    check_summary(lab,[k for k in lab.report['checks'] if k.startswith('dds_')],'Native DDS checks')
