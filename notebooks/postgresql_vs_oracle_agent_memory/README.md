# PostgreSQL versus Oracle AI Database for agent memory

[Open the notebook](postgresql_vs_oracle_agent_memory.ipynb) to compare memory writes and retrieval using Oracle AI Database 26ai and PostgreSQL with pgvector and pg_textsearch. It demonstrates local ONNX inference, SQL property graphs, hybrid retrieval, transaction visibility, and database access controls.

All memories are synthetic. The relevance fixture contains 100 memories and eight questions. Both engines receive identical Oracle-generated vectors and BGE reranking scores; PostgreSQL's inference is external in this experiment. The notebook makes no paid model-service calls.

## Files

| File | Purpose |
| --- | --- |
| `postgresql_vs_oracle_agent_memory.ipynb` | Walkthrough with saved execution outputs |
| `lab.py` | Connections, model loading, database setup, retrieval, and cleanup |
| `corpus.py` | 100 synthetic memories, eight questions, and fixture validation |
| `qrels.json` | All 800 relevance scores, rationales, and the grading rubric |
| `notebook_display.py` | Highlighted source, result tables, and ranking explanations |
| `review_experiments.py` | Ten-candidate evaluation, inline query embedding, and Oracle Text experiments |
| `dds_experiment.py` | Optional native Deep Data Security demonstration |
| `Dockerfile.postgres` | Local PostgreSQL image with pgvector and pg_textsearch |
| `.env.example` | Configuration keys to add to the repository's `.env` |
| `execute_notebook.py` | Runs all notebook cells and saves their outputs |
| `results/verification.json` | Recorded reference run for inspecting results without a database |

Download the whole folder and keep its supporting files together.

## Prerequisites

Use a Python 3.11+ Jupyter kernel and development instances of Oracle AI Database 26ai and PostgreSQL with pgvector and pg_textsearch. Docker is needed if you use the supplied PostgreSQL image or the optional local DDS example.

Use a non-SYS schema owner without `EXEMPT ACCESS POLICY`. It needs tablespace quota; `CREATE SESSION`, `CREATE TABLE`, `CREATE PROCEDURE`, and `CREATE PROPERTY GRAPH`; Oracle Text access through `CTXAPP`; and `EXECUTE ON DBMS_RLS`. Loading a missing model also requires `CREATE MINING MODEL` and execute access to `DBMS_VECTOR`. Wallet-based connections aren't configured by this example.

The PostgreSQL account needs extension and role-administration privileges for setup. The recorded run uses Oracle Free 23.26.3.0.0, PostgreSQL 18.6, pgvector 0.8.7, and pg_textsearch 1.5.0.

## Database setup

The notebook uses the stable Oracle memory table `PG_ORACLE_MEMORY` and PostgreSQL table `postgres_oracle.memory`. Supporting Oracle objects use fixed `PG_ORACLE_*` names; PostgreSQL uses the `postgres_oracle` schema and `postgres_oracle_reader` role. Setup recreates these notebook objects, clearing leftovers from an interrupted run. A session lock allows one active notebook run per PostgreSQL database; cleanup or shutting down its kernel releases the lock. Existing models and unrelated tables are preserved.

If `ALL_MINILM_L12_V2` is missing, the notebook downloads and loads Oracle's augmented MiniLM ONNX model, about 130 MB. This requires outbound HTTPS to Oracle Object Storage. Set `EMBEDDING_ONNX_FILE` to use a local artifact instead. An existing model is reused and checked for 384-dimensional output.

The BGE reranker must already be loaded as `BGE_RERANKER`, or you must set `RERANKER_ONNX_FILE` to an augmented ONNX export of `BAAI/bge-reranker-base`. Follow the conversion and local validation sections of the [reranker preparation notebook](../vecdb/reranking/load-model-for-in-database-reranking.ipynb); its VecDB REST and cloud upload steps aren't needed here. Raw Hugging Face weights are not the required augmented artifact.

### Start the databases

If your local containers already exist, start them:

```bash
docker start oracle-free pg-oracle-postgres
docker ps
```

Wait for Oracle to show `healthy`. For other deployments, make sure both services are accepting connections before running the notebook.

If you need a new PostgreSQL instance, run these commands from the Developer Hub repository root:

```bash
docker build \
  -f notebooks/postgresql_vs_oracle_agent_memory/Dockerfile.postgres \
  -t pg-oracle-postgres:pg18-bm25 \
  notebooks/postgresql_vs_oracle_agent_memory
```

Set `POSTGRES_PASSWORD` privately in your shell, then create the container:

```bash
docker run -d --name pg-oracle-postgres \
  -p 127.0.0.1:5547:5432 \
  -e POSTGRES_PASSWORD -e POSTGRES_DB=pg_oracle \
  pg-oracle-postgres:pg18-bm25
```

Use that password in `PG_DSN` below. The image includes both PostgreSQL extensions and configures pg_textsearch in `shared_preload_libraries`. The notebook enables the extensions if needed. An Oracle development database must already be available.

## Python setup

The notebook's first code cell installs pinned `oracledb`, `python-dotenv`, and `psycopg` packages into the running kernel, so no separate dependency install is needed for interactive use.

Add these keys to the `.env` at the Developer Hub repository root, preserving any existing connection values:

```dotenv
DB_USER=
DB_PASSWORD=
DB_DSN=localhost:1521/FREEPDB1
PG_DSN="host=127.0.0.1 port=5547 dbname=pg_oracle user=postgres password=your_local_password"
# Only needed if the reranker is not already loaded:
# RERANKER_ONNX_FILE=/absolute/path/to/bge_reranker_base.onnx
# Optional local embedding artifact instead of the automatic download:
# EMBEDDING_ONNX_FILE=/absolute/path/to/all_MiniLM_L12_v2.onnx
# Optional DDS demo against an existing local Oracle Free container:
# PG_ORACLE_DDS_CONTAINER=oracle-free
# PG_ORACLE_DDS_PDB=FREEPDB1
```

The helper searches upward from the notebook folder for the nearest `.env`; exported environment variables take precedence. An existing folder-local `.env` still works and takes precedence over the repository file. `PG_ORACLE_ENV_FILE` can select a different file explicitly. Keep credentials out of notebook cells and outputs.

Open the notebook from the repository root:

```bash
jupyter lab notebooks/postgresql_vs_oracle_agent_memory/postgresql_vs_oracle_agent_memory.ipynb
```

Select a Python 3.11+ kernel and run the cells in order. Restart the kernel before a full rerun, or if pip replaces a package already imported by the kernel.

For command-line execution, run from the repository root:

```bash
python -m pip install nbclient==0.11.0 nbformat==5.11.1 ipykernel==7.4.0
python notebooks/postgresql_vs_oracle_agent_memory/execute_notebook.py
```

The runner uses that Python interpreter for its kernel and saves the notebook outputs.

## Check the results

Each completed run writes `results/run-<timestamp>.json`, which this folder's `.gitignore` excludes. It records database and extension versions, model metadata, source hashes, per-query rankings, and pass/fail checks. The included `results/verification.json` is a reference run; a normal execution leaves it intact.

Both retrieval pipelines use exact cosine search and SQL RRF with constant 60. BGE runs through `DBMS_VECTOR_CHAIN.UTL_TO_RERANK` with `provider=database`. Retrieval admits 79 active Acme memories, excluding nine superseded memories and 12 from another tenant. [qrels.json](qrels.json) contains a grade and rationale for all 800 question-memory pairs. These are editorial judgments, without independent human assessment or a separate set of questions reserved for final evaluation. The experiment does not measure latency, throughput, approximate-index recall, or managed-service performance. Oracle graph queries use SQL property graphs; PostgreSQL uses relational edges without Apache AGE. The VPD/RLS checks enforce a fixed Acme predicate, while the optional DDS example tests end-user access.

## Read the evaluation

Use the ranking selectors to inspect a question, engine, and retrieval method. Tables show relevance grades, missing memories, and changes in position after reranking. Expand the source blocks to inspect the implementation.

The judgment and ranking inspection cells work independently after a kernel restart. They use current-kernel results when available or load `results/verification.json` without a database connection. Each view labels its source and timestamp; hash checks prevent combining saved rankings with different memories or judgments.

Relevance grades use a task-specific 0-3 rubric: direct answer (3), substantive support (2), useful qualification or prerequisite (1), and irrelevant or ineligible (0). Four-level grading is common in [TREC evaluations](https://trec.nist.gov/data/deep2021.html), but the label meanings and binary-relevance thresholds vary by task.

The notebook calculates nDCG with exponential gain `2**grade - 1` (gains 0, 1, 3, 7) and discount `1 / log2(rank + 1)`, with ranks starting at 1. It normalizes against the ideal top-k ordering of all judged memories. This is an [established nDCG variant](https://docs.pytorch.org/ignite/master/generated/ignite.metrics.rec_sys.NDCG.html); [scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html) uses supplied relevance values directly, so raw grades there produce linear-gain scores.

Recall counts every grade >= 1 equally. Each metric is computed per question and averaged equally across the eight questions. nDCG@5 assesses ordering in the first five results; Recall@8 assesses coverage in the first eight. The ten-candidate evaluation also reports nDCG@10 and Recall@10.

## Optional Deep Data Security example

Uncomment `PG_ORACLE_DDS_CONTAINER` and `PG_ORACLE_DDS_PDB` in `.env` to run the native DDS example on a local Oracle Free development container you administer. With these settings absent, the cell records `not_run` and the other experiments still run.

Setup uses SQL*Plus OS authentication through `docker exec` to create temporary end users, data roles, and data grants. Access checks connect as those end users; generated passwords remain in memory.

Support and finance issue the same SELECT without a tenant predicate. Both see only Acme rows, while support sees one restricted payment amount masked as NULL and finance sees both values. The test also verifies that `OR 1=1` cannot expand the visible rows and that an incorrect password is rejected. Temporary DDS objects are removed even if a check fails.

This example tests local DDS authentication and row/cell grants on Free 23.26.3.0.0. It does not validate external IAM tokens, pooled identity propagation, or agent delegation. The fixed-predicate VPD/RLS tests are separate from DDS.

## Cleanup

The final cell removes the notebook's tables and supporting objects, then closes both connections. Run it after an earlier cell fails while the kernel is available. After a lost kernel, the next setup resets the same fixed objects. Existing models remain loaded. Deleting result files does not remove database objects.

After finishing with local containers, stop them without deleting their data:

```bash
docker stop oracle-free pg-oracle-postgres
```

## References

- [UTL_TO_RERANK](https://docs.oracle.com/en/database/oracle/oracle-database/26/vecse/utl_to_rerank-dbms_vector_chain.html)
- [DDS local authentication setup](https://docs.oracle.com/en/database/oracle/oracle-database/26/ddscg/configure-database-local-end-user-authentication.html)
