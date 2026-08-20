# Hybrid-Search RAG over PDF Lecture Notes

A retrieval-augmented generation system built on Postgres. PDFs are chunked with docling,
embedded with OpenAI, and stored in a single `pgvector` table that serves **two** retrieval
strategies at once — dense vector similarity and Postgres full-text search — fused with
reciprocal rank fusion and answered by a chat model that cites its sources.

No vector-database service, no separate search index, no orchestration framework. One
Postgres table and about 600 lines of Python, plus a dependency-free HTML page to drive it.

---

## What it does

```bash
curl -X POST http://127.0.0.1:8000/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "what is backpropagation?", "top_k": 3}'
```

```json
{
  "answer": "Backpropagation is the method that computes the gradient of a neural network's loss with respect to all its parameters using the chain rule of calculus, doing so efficiently [1]. It works by running a forward pass to compute predictions, then a backward pass to propagate errors and update weights [3].",
  "sources": [
    {"citation": 1, "id": 491, "source": "Lecture-08_26.pdf", "page_numbers": [36], "headings": ["Backpropagation"]},
    {"citation": 2, "id": 609, "source": "Lecture-12_26.pdf", "page_numbers": [17], "headings": ["Forward Propagation"]},
    {"citation": 3, "id": 495, "source": "Lecture-08_26.pdf", "page_numbers": [39], "headings": ["Backpropagation"]}
  ],
  "model": "gpt-5.4-nano"
}
```

Every claim carries a bracketed citation that resolves to a filename, a page number, and the
section heading it came from. The chunker collects that provenance at ingestion time
specifically so answers stay traceable.

**Current corpus:** 879 chunks across 23 documents, averaging 514 characters per chunk.

The corpus itself is not in this repository — those documents are third-party lecture
material. `data/` is gitignored; drop your own PDFs in and run the ingest below.

---

## Why hybrid retrieval

Dense embedding search understands meaning but is weak on rare literal tokens. Keyword search
is the reverse. The interesting question is not which is better — it is what each one *misses*.

Query: **`AdamW`** (a rare, exact term)

| chunk id | dense rank | sparse rank | **hybrid rank** |
|---|---|---|---|
| 498 | 1 | 1 | **1** |
| 502 | **44** | 2 | **2** |
| 215 | 2 | *no match* | **3** |

Chunk 502 is a relevant passage about optimizers that dense retrieval buried at rank 44 —
outside anything a user would ever see. Keyword search ranked it 2nd. Fusion recovered it.

Chunk 215 shows the same effect in reverse: keyword search never matched it at all, and dense
retrieval carried it.

Neither arm alone produces this ranking. That is the entire argument for the architecture,
and it is measured on this corpus rather than asserted.

---

## Architecture

```
INGESTION (run once)                QUERY (per request)
                                    
PDF                                 HTTP request
 │                                   │
 ├─ docling HybridChunker            ├─ RAGPipeline
 │    512-token chunks               │    │
 │    + page numbers, headings       │    ├─ HybridRetriever
 │                                   │    │    ├─ dense_search  → pgvector  <#>  (HNSW)
 ├─ OpenAI text-embedding-3-small    │    │    ├─ sparse_search → tsvector  @@  (GIN)
 │    1536-dim, batched              │    │    └─ reciprocal_rank_fusion
 │                                   │    │
 └─ Postgres ──────────────────────► │    └─ AnswerGenerator → OpenAI chat + citations
      documents(                     │
        embedding vector(1536),      └─ FastAPI response
        fts tsvector GENERATED
      )
```

The two entry points never import each other. `ingest.py` fills the database and exits;
`main.py` serves queries and never touches docling.

**One table holds both representations.** The `fts` column is
`GENERATED ALWAYS AS (to_tsvector('english', content)) STORED`, so the keyword index updates
inside the same transaction as the insert. There is no second index to rebuild, no sync job,
and no window where the two retrieval arms disagree about what exists.

---

## Engineering decisions

Each of these was a real fork in the road. The measurements come from this corpus.

### The keyword query must OR its terms, not AND

`plainto_tsquery` and `websearch_to_tsquery` both AND every term, so a chunk must contain all
of them. For the query *"how does backpropagation compute gradients"*:

| query builder | chunks matched |
|---|---|
| `plainto_tsquery` | 6 |
| `websearch_to_tsquery` | 6 |
| OR-ed lexemes (this implementation) | **148** |

With 50 candidates requested per arm, the AND forms hand fusion six documents and the sparse
arm contributes nothing — while still returning plausible-looking results. This is the kind of
failure that never raises an exception.

The implementation extracts lexemes with `to_tsvector` and joins them with `|`, which reuses
Postgres's own tokenizer. Query-side stemming and stopword removal therefore match the stored
column *by construction* rather than by convention.

It is also injection-proof as a side effect — `to_tsvector` emits lexemes, never operators:

```
input:  a & b | c ! (d) ':*
parsed: 'b' | 'c' | 'd'
```

### Fuse on rank, never on score

`ts_rank_cd` returns values around 0.1–0.3. Inner-product similarities live on an unrelated
scale. Averaging them is arithmetically valid and semantically meaningless. Reciprocal rank
fusion uses only ordinal position:

```
score(doc) = Σ  1 / (k + rank)     k = 60
```

This keeps `reciprocal_rank_fusion` a **pure function over id lists** — no database, no
embeddings, no knowledge of what the arms are. It is unit-testable by hand, and swapping a
retriever is a local change.

### Over-fetch, then trim

Each arm returns 50 candidates; fusion returns 10. Fusing only the top 10 would discard
exactly the agreement cases fusion exists to find — the chunk one arm ranked 2nd and the other
ranked 44th.

### Length normalization, because Postgres FTS has no IDF

This is the real cost of using Postgres instead of a dedicated BM25 engine, and it is worth
stating plainly. `ts_rank_cd` weighs every term equally — it has no idea that *gradient* is
ubiquitous in this corpus while *backpropagation* is specific.

Default ranking put the chunk beginning *"Backpropagation computes the gradient of…"* in
**4th place**, behind a passage on Gradient Boosting. Enabling normalization mode 1 (divide by
`1 + log(length)`) lifts it to 2nd, losing first place by 0.0004.

That is a mitigation, not a fix. It is accepted here because fusion consumes rank order rather
than scores, and because the dense arm covers exactly the multi-word natural-language queries
where the absence of IDF hurts most. If sparse retrieval later proves to be dead weight in
fused results, `pg_search` provides true BM25 as a Postgres extension and only
`keyword_search` would change.

### Deterministic ordering

Score ties are common. They are broken on `id` in SQL and on `id` in the Python sort, so
identical runs produce identical output rather than quietly reshuffling.

---

## Running it

Requires Docker, Python 3.13, [uv](https://docs.astral.sh/uv/), and an OpenAI API key.

```bash
uv sync
echo "OPENAI_API_KEY=sk-..." > .env

docker compose -f docker/docker-compose.yml up -d   # Postgres + pgvector on :5555

# put your own PDFs in data/ (empty in a fresh clone), then — this costs embedding API calls
uv run python ingest.py

uv run fastapi dev main.py                          # docs at http://127.0.0.1:8000/docs
```

Then open `web/index.html` in a browser to ask questions through a page instead of curl. It is
a single static file — no build step, no `node_modules` — and talks to the API above.

Re-ingesting a file replaces its chunks rather than duplicating them: `metadata["source"]`
acts as document identity and is deleted by before insert.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness, plus a real Postgres round-trip returning the chunk count |
| `POST` | `/search` | Retrieval only — no chat call, no generation cost |
| `POST` | `/answer` | Retrieval and a cited answer |

`/search` exists separately on purpose. When an answer is wrong, the first question is always
*"did retrieval find the right passage, or did the model fumble a passage it had?"* — and two
endpoints answer it directly.

---

## Layout

```
ingest.py            ingestion pipeline; run once
RAG_pipeline.py      composes retrieval + generation
main.py              FastAPI app
source/
  config.py          all tunables; loads .env at import
  doc_processing.py  docling chunking + provenance metadata
  embeddings.py      OpenAI embeddings, batched
  vector_store.py    all SQL — dense, sparse, hydration, deletion
  retrieval.py       reciprocal rank fusion + HybridRetriever
  generate.py        grounded answer generation with citations
eval/                evaluation harness (in progress)
  common.py          stable chunk keys, jsonl io, run provenance
  metrics.py         hit rate, recall, MRR, nDCG — implemented by hand
web/index.html       single-file browser UI, no build step
docker/init.sql      schema: HNSW index, generated tsvector, GIN index
docs/evaluation.md   the evaluation plan this repo is currently working through
docs/frontend-guide.md  building a React/Vite UI against this API
```

`eval/` sits beside `source/` rather than inside it: it is a tool for developing the system,
not part of the system. Nothing in `source/` imports it.

---

## Limitations

Stated deliberately — these are known, not overlooked.

- **No automated tests.** Correctness has been verified by hand and by measurement. This is the
  most significant gap.
- **Retrieval is not yet scored.** There is no labelled question set, so retrieval quality is
  demonstrated by example rather than measured across queries. This is actively being built:
  the plan is written out in [`docs/evaluation.md`](docs/evaluation.md), and the foundations —
  stable chunk keys that survive a re-ingest, and hit rate / recall / MRR / nDCG implemented by
  hand — are in `eval/`. The golden question set is the next step, and the headline
  dense-vs-sparse-vs-hybrid table depends on it.
- **Single database connection.** `VectorStorage` holds one `psycopg` connection, so concurrent
  requests serialise on it. Fine at this scale; `psycopg_pool` is the contained fix.
- **Chunks can outlive their source files.** Deleting a PDF leaves its rows in Postgres, where
  retrieval will cite a path that no longer exists. Detectable with one query; not yet
  automated.
- **English only.** The `fts` column hardcodes the `english` text-search configuration, and
  changing it requires a schema migration rather than a config edit.
- **No conversation memory.** Each request is independent, so follow-up questions that depend
  on prior turns will not resolve.
- **The answer is not streamed.** `/answer` returns once the chat model has finished, so the
  browser page sits on "Thinking…" for the whole call rather than rendering tokens as they
  arrive.

---

## Stack

Python 3.13 · Postgres 17 + pgvector · docling · OpenAI (`text-embedding-3-small`,
`gpt-5.4-nano`) · FastAPI · psycopg 3 · uv

Deliberately small. The only framework is the web framework; retrieval, fusion, and prompting
are written directly against the underlying APIs, which is what makes each decision above
inspectable and each measurement reproducible. The retrieval metrics in `eval/` are written by
hand for the same reason — the formula behind a reported number is a thing worth being able to
defend.
