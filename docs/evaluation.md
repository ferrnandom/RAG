# Phase 3 — Evaluation, step by step

A build-along guide. Every step says what to create, gives the code, explains why it is shaped
that way, and ends with a check you can run.

Written to be transferable — this is the structure you would set up for a client, not a
throwaway script.

**Build order matters.** Steps 1–4 need no LLM judge and produce the single most valuable
artifact in the project: the dense vs sparse vs hybrid table. Stop there and you are already
ahead of most RAG projects. Steps 5–9 add generation quality, refusal, and the regression
harness.

---

## Why this phase decides whether you have a product

Retrieval sets a hard ceiling on everything downstream. If the right passage is not in the
context, no prompt engineering recovers it. So when an answer is wrong the first question is
always *"did retrieval fail, or did the model fumble a passage it had?"* — and you cannot
answer that without measuring the two separately. `/search` and `/answer` are separate
endpoints for exactly this reason.

Without evaluation, every change to `chunk_max_tokens`, `candidate_k`, `rrf_k` or the prompt
is a guess. With it, each becomes a measurement.

---

## Step 0 — Layout and dependencies

```
eval/
  __init__.py
  common.py          # chunk keys, jsonl io, config snapshot
  metrics.py         # recall, mrr, ndcg, precision -- written by hand
  build_dataset.py   # LLM-assisted question generation + bias filter
  run_retrieval.py   # the headline table
  judges.py          # LLM judges + kappa validation
  run_generation.py  # faithfulness, citations, refusal
  compare.py         # diff two result files
  dataset/
    golden_v1.jsonl
    negatives_v1.jsonl
  results/
    2026-08-15T1422.json
```

`eval/` sits beside `source/`, not inside it — it is a tool for developing the system, not part
of the system.

Everything you need is already installed (`beir`, `pytrec_eval`, `numpy`, `scikit-learn`).
Nothing new to add.

---

## Step 1 — Foundations: stable keys and chunk access

### 1a. Add one method to `VectorStorage`

The eval layer needs every chunk with its metadata. Per project convention, SQL lives in
`source/vector_store.py`:

```python
    def all_chunks(self) -> list[dict[str, Any]]:
        """Every chunk with metadata, ordered by id. Used by the evaluation harness."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, content, metadata FROM documents ORDER BY id")
            return cur.fetchall()
```

### 1b. `eval/common.py`

```python
"""Shared helpers for the evaluation harness."""

import json
import subprocess
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).parent


def chunk_key(metadata: dict[str, Any]) -> str:
    """Stable identifier for a chunk, unlike the Postgres id.

    Postgres ids are GENERATED ALWAYS AS IDENTITY -- they change on every
    re-ingest. A dataset labelled with ids silently rots. This key survives
    re-ingestion as long as chunking parameters stay the same.
    """
    return f"{Path(metadata['source']).name}::{metadata['chunk_index']}"


def rows_to_keys(rows: list[dict[str, Any]]) -> list[str]:
    """Convert retrieval results (which carry metadata) into ranked chunk keys."""
    return [chunk_key(row["metadata"]) for row in rows]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def git_sha() -> str:
    """Short commit hash, or 'uncommitted' if the repo has no commits yet."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "uncommitted"
```

### Why `chunk_key` is the most important function here

Your `id` column is `BIGINT GENERATED ALWAYS AS IDENTITY`. Re-ingest a document and its chunks
get **new ids**. A golden dataset labelled with ids points at the wrong passages after any
re-ingest — and it fails silently, producing plausible-looking scores that mean nothing.

`Lecture-08_26.pdf::12` survives re-ingestion. It does **not** survive a change to
`chunk_max_tokens`, because chunk boundaries move. If you change chunk size, re-verify labels.

**Check:**

```python
from source import VectorStorage
from eval.common import chunk_key

store = VectorStorage()
chunks = store.all_chunks()
keys = [chunk_key(c["metadata"]) for c in chunks]
assert len(keys) == len(set(keys)), "keys are not unique"
print(len(keys), "chunks,", keys[0])
store.close()
```

---

## Step 2 — `eval/metrics.py`

Implement these by hand once. They are four lines each, and understanding them is the
difference between reporting a number and defending it.

```python
"""Retrieval metrics, implemented directly.

Written by hand deliberately: these are the numbers you will defend in front of a
client, and the formula matters. Reported figures come from pytrec_eval (via beir),
which is the standard implementation -- these exist so you know what it computes.
"""

import math


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant chunk is in the top k. Blind to position."""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of all relevant chunks that appear in the top k."""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top k that is relevant. Drives context cost, not answerability."""
    if k == 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / k


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / rank of the FIRST relevant chunk. Sees only the first hit."""
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant:
            return 1.0 / rank
    return 0.0


def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(rank + 1) for rank, g in enumerate(gains, start=1))


def ndcg_at_k(retrieved: list[str], grades: dict[str, int], k: int) -> float:
    """Graded relevance, position-discounted.

    Uses gain = 2^rel - 1, the TREC convention that pytrec_eval implements, so
    hand-computed values match the reported ones. The other common variant uses
    gain = rel and produces different numbers -- this is exactly why you should
    not invent your own nDCG for anything you publish.
    """
    gains = [2 ** grades.get(key, 0) - 1 for key in retrieved[:k]]
    ideal = [2 ** g - 1 for g in sorted(grades.values(), reverse=True)[:k]]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg else 0.0
```

### Which metric answers which question

| Metric | Answers | Blind to |
|---|---|---|
| Hit Rate@k | Did we find it at all? | position |
| Recall@k | What share of relevant passages did we get? | position |
| Precision@k | How much junk came along? | *nothing — but junk is survivable* |
| MRR | How high was the first hit? | everything after the first hit |
| nDCG@k | Graded quality, position-aware | harder to explain to non-technical buyers |

**The RAG-specific rule: optimise Recall first, Precision second.** A missing passage is
unrecoverable; an irrelevant one is usually ignored by the generator. This is the opposite of
a classic search product.

But recall is trivially gamed by raising `k`, and `k` costs tokens, latency, and attention
(models under-use passages buried mid-context). The real question is **the smallest `top_k` at
which recall stops improving** — Step 9 plots that curve.

**Check** — verify by hand against a case you can compute mentally:

```python
from eval.metrics import *

retrieved = ["a", "b", "c", "d"]
assert recall_at_k(retrieved, {"a", "c"}, 4) == 1.0
assert recall_at_k(retrieved, {"a", "z"}, 4) == 0.5
assert reciprocal_rank(retrieved, {"c"}) == 1 / 3
assert hit_rate_at_k(retrieved, {"z"}, 4) == 0.0
assert round(ndcg_at_k(retrieved, {"a": 2, "c": 1}, 4), 4) == 1.0  # already ideal order
print("metrics ok")
```

---

## Step 3 — `eval/build_dataset.py`

### What a labelled example looks like

```json
{
  "id": "q001",
  "question": "How does a network figure out which weights to change after a wrong prediction?",
  "relevant": [{"chunk_key": "Lecture-08_26.pdf::12", "grade": 2}],
  "answer": "It applies the chain rule, running a forward pass to cache activations and a backward pass to propagate error signals.",
  "type": "factual",
  "answerable": true,
  "overlap": 0.21
}
```

`grade` is graded relevance — `2` fully answers, `1` partially. Binary works, but grades let
you use nDCG, which distinguishes the perfect chunk at rank 3 from a vaguely related one there.

### The code

```python
"""Generate golden questions from chunks, then filter for lexical bias."""

import argparse
import random
from typing import Literal

from pydantic import BaseModel

from eval.common import EVAL_DIR, chunk_key, write_jsonl
from source import CONFIG, VectorStorage
from openai import OpenAI

GENERATOR_MODEL = "gpt-5.4-mini"   # stronger than the answering model on purpose

PROMPT = """You write evaluation questions for a retrieval system over university \
lecture notes.

Given one passage, write ONE question that this passage answers.

Critical rules:
- Write it as a student would ask BEFORE having read the passage.
- Do NOT reuse distinctive terminology from the passage. Paraphrase into everyday words.
  (If the passage says "stochastic gradient descent", ask about "updating weights using \
small batches of data".)
- It must be answerable from this passage alone, and specific enough that a different \
passage would not answer it.
- Avoid questions answerable from general knowledge without the passage.
"""


class GeneratedQuestion(BaseModel):
    reasoning: str                      # first: forces thinking before committing
    question: str
    answer: str
    question_type: Literal["factual", "definitional", "comparative", "multi_hop"]


def lexical_overlap(question: str, passage: str) -> float:
    """Share of question words that appear literally in the passage.

    High overlap means the question copied the passage's vocabulary, which
    unfairly favours keyword retrieval and hides real-world failure.
    """
    q = {w.strip(".,?!:;()").lower() for w in question.split()}
    q = {w for w in q if len(w) > 3}          # ignore stopword-ish short tokens
    if not q:
        return 0.0
    p = {w.strip(".,?!:;()").lower() for w in passage.split()}
    return len(q & p) / len(q)


def build(n: int, max_overlap: float, seed: int) -> None:
    random.seed(seed)
    client = OpenAI()
    store = VectorStorage()

    chunks = [c for c in store.all_chunks() if len(c["content"]) > 300]
    sample = random.sample(chunks, min(n, len(chunks)))

    records, dropped = [], 0
    for i, chunk in enumerate(sample, start=1):
        completion = client.chat.completions.parse(
            model=GENERATOR_MODEL,
            temperature=0,
            max_completion_tokens=500,
            response_format=GeneratedQuestion,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"Passage:\n\n{chunk['content']}"},
            ],
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            continue

        overlap = lexical_overlap(parsed.question, chunk["content"])
        if overlap > max_overlap:
            dropped += 1
            continue

        records.append({
            "id": f"q{len(records) + 1:03d}",
            "question": parsed.question,
            "relevant": [{"chunk_key": chunk_key(chunk["metadata"]), "grade": 2}],
            "answer": parsed.answer,
            "type": parsed.question_type,
            "answerable": True,
            "overlap": round(overlap, 3),
        })
        print(f"[{i}/{len(sample)}] kept={len(records)} dropped={dropped}", end="\r")

    write_jsonl(EVAL_DIR / "dataset" / "golden_v1.jsonl", records)
    store.close()
    print(f"\nwrote {len(records)} questions, dropped {dropped} for lexical overlap")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--max-overlap", type=float, default=0.45)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    build(args.n, args.max_overlap, args.seed)
```

### The trap this code exists to avoid

**LLM-generated questions reuse the vocabulary of the passage they came from.** Show a model a
chunk containing "AdamW decoupled weight decay" and it writes *"What is AdamW decoupled weight
decay?"* — a question that is nearly a substring of the target.

Keyword search then looks superb. You conclude sparse retrieval is excellent, ship it, and
real users asking *"which optimizer avoids overfitting?"* get nothing.

The paraphrase instruction and the `lexical_overlap` filter are both mitigations. Generate
~120 and expect to keep ~80.

### Then curate by hand

Read every kept question. Delete any that are ambiguous, answerable from any chunk, or that
the paraphrase instruction mangled into nonsense. **Budget an hour.** This hour is the highest
value-per-minute work in the whole phase — the dataset is what nobody else can copy.

While curating, add a second relevant chunk with `"grade": 1` wherever another passage
partially answers. That is what makes nDCG meaningful.

### How many, and what that buys

| Size | Detects differences of |
|---|---|
| 30 | catastrophic only |
| **50–100** | **~10 points — the realistic target** |
| 200+ | ~5 points |

With 50 questions and a score near 0.80, the standard error is `sqrt(0.8×0.2/50) ≈ 5.7%`, so
the 95% interval is roughly ±11 points. **A move from 0.78 to 0.83 on 50 questions is noise.**
Step 4 includes a paired bootstrap so you can say something defensible instead.

**Hold out a test split you do not look at while tuning.** 60/40 is fine at this size.

---

## Step 4 — `eval/run_retrieval.py` (the headline table)

```python
"""Compare dense, sparse, and hybrid retrieval on the golden dataset."""

import argparse

import numpy as np
from beir.retrieval.evaluation import EvaluateRetrieval

from eval.common import EVAL_DIR, chunk_key, read_jsonl, rows_to_keys
from RAG_pipeline import RAGPipeline

K_VALUES = [1, 3, 5, 10]


def paired_bootstrap(a: list[float], b: list[float], n: int = 10_000) -> float:
    """P(system A scores higher than system B), same queries for both.

    Paired because both systems answer the SAME questions -- far more
    sensitive than comparing two independent averages.
    """
    diffs = np.array(a) - np.array(b)
    idx = np.random.randint(0, len(diffs), (n, len(diffs)))
    return float((diffs[idx].mean(axis=1) > 0).mean())


def retrieve(pipeline: RAGPipeline, system: str, query: str, k: int) -> list[str]:
    """Ranked chunk keys from one retrieval arm."""
    if system == "dense":
        return rows_to_keys(pipeline.hybrid_retriever.dense_search(query, k))

    if system == "sparse":
        ids = [i for i, _ in pipeline.hybrid_retriever.sparse_search(query, k)]
        rows = pipeline.vector_store.get_by_ids(ids)
        return [chunk_key(rows[i]["metadata"]) for i in ids if i in rows]

    return rows_to_keys(pipeline.search(query, top_k=k))


def main(dataset: str, k: int) -> None:
    questions = read_jsonl(EVAL_DIR / "dataset" / dataset)
    questions = [q for q in questions if q.get("answerable", True)]
    pipeline = RAGPipeline()

    qrels = {
        q["id"]: {r["chunk_key"]: r["grade"] for r in q["relevant"]}
        for q in questions
    }

    runs, per_query = {}, {}
    for system in ("dense", "sparse", "hybrid"):
        runs[system], per_query[system] = {}, []
        for q in questions:
            keys = retrieve(pipeline, system, q["question"], k)
            # pytrec_eval sorts by score; rank order becomes a descending score
            runs[system][q["id"]] = {key: float(k - i) for i, key in enumerate(keys)}

            relevant = {r["chunk_key"] for r in q["relevant"]}
            per_query[system].append(
                len(set(keys[:k]) & relevant) / len(relevant) if relevant else 0.0
            )
        print(f"{system:7} done")

    print(f"\n{'system':8} {'Recall@10':>10} {'NDCG@10':>9} {'MRR':>7} {'P@10':>7}")
    scores = {}
    for system in ("dense", "sparse", "hybrid"):
        ndcg, _map, recall, precision = EvaluateRetrieval.evaluate(
            qrels, runs[system], K_VALUES
        )
        mrr = EvaluateRetrieval.evaluate_custom(qrels, runs[system], [k], metric="mrr")
        scores[system] = {**ndcg, **recall, **precision, **mrr}
        print(
            f"{system:8} {recall['Recall@10']:>10.3f} {ndcg['NDCG@10']:>9.3f} "
            f"{mrr[f'MRR@{k}']:>7.3f} {precision['P@10']:>7.3f}"
        )

    print("\npaired bootstrap, P(hybrid > arm):")
    for arm in ("dense", "sparse"):
        p = paired_bootstrap(per_query["hybrid"], per_query[arm])
        print(f"  vs {arm:7} {p:.3f}" + ("  significant" if p > 0.95 else "  NOT significant"))

    pipeline.close()
    return scores


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="golden_v1.jsonl")
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()
    main(args.dataset, args.k)
```

### Reading the output

```
system     Recall@10   NDCG@10     MRR    P@10
dense          0.812     0.634   0.591   0.094
sparse         0.735     0.548   0.502   0.086
hybrid         0.874     0.702   0.661   0.101

paired bootstrap, P(hybrid > arm):
  vs dense    0.981  significant
  vs sparse   0.998  significant
```

*(illustrative shape — your numbers will differ)*

**If hybrid does not beat both arms, report that honestly.** It is a genuine finding, not a
reason to tune `rrf_k` until the table looks better. Tuning against your own test set produces
a number that is optimistic by an unknown amount.

Also break the table down by `type` — hybrid usually wins on rare-term and multi-hop questions
and ties on plain factual ones. That detail persuades far more than one aggregate.

---

## Step 5 — Refusal, the test that matters most

Everything so far measures questions the corpus *can* answer. **Production failures are mostly
the other case.**

### 5a. Make refusal machine-readable

Modify `source/generate.py` to use structured output. This is a genuine product improvement,
not test scaffolding — the API can render "not found" differently from an answer.

```python
from pydantic import BaseModel


class GroundedAnswer(BaseModel):
    reasoning: str
    answer: str
    citations: list[int]
    answer_found: bool
```

In `generate_answer`, swap `.create()` for `.parse()`:

```python
        completion = self.client.chat.completions.parse(
            model=self.model,
            temperature=CONFIG.chat_temperature,
            max_completion_tokens=CONFIG.max_answer_tokens,
            response_format=GroundedAnswer,
            messages=[...same as now...],
        )

        message = completion.choices[0].message
        if message.refusal:                       # safety refusal -> parsed is None
            return {"answer": message.refusal, "sources": [],
                    "answer_found": False, "model": self.model}

        result = message.parsed
        cited = set(result.citations)
        return {
            "answer": result.answer,
            "sources": [s for s in self._source(chunks) if s["citation"] in cited],
            "answer_found": result.answer_found,
            "model": self.model,
        }
```

Add to the system prompt: *"Set answer_found to false if the passages do not contain the
answer."* Add `answer_found: bool` to the `Answer` model in `main.py`.

Filtering `sources` by `citations` also fixes a real UX problem — today you return all 10
retrieved chunks as "sources" even when the model used two.

### 5b. Write the negative set by hand

**Do not generate these with an LLM** — the whole point is questions your corpus cannot answer,
and a model shown your corpus will not reliably produce them. 20–30 in three flavours:

| Flavour | Example |
|---|---|
| **Off-topic** | "What is the capital of France?" |
| **Plausible but absent** | "What did Lecture 15 say about diffusion models?" (no Lecture 15 exists) |
| **Adjacent and tempting** | "What learning rate does the course recommend for AdamW?" — AdamW is discussed, this fact is not |

The third kind is the realistic one and the hard one: the model has related context plus strong
priors, which is exactly when it invents.

```json
{"id": "n001", "question": "What is the capital of France?", "answerable": false, "flavour": "off_topic"}
```

Two metrics, reported together:

- **Refusal rate** — of unanswerable questions, how many were declined. Target >90%.
- **False refusal rate** — of *answerable* questions, how many were wrongly declined.

Report both or neither. A system that refuses everything scores perfectly on the first.

---

## Step 6 — `eval/judges.py`

```python
"""LLM judges for generation quality, plus validation against human labels."""

import re
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

JUDGE_MODEL = "gpt-5.5"          # deliberately stronger than the generator


class Claims(BaseModel):
    claims: list[str]


class ClaimVerdict(BaseModel):
    reasoning: str                                    # FIRST: reason before committing
    verdict: Literal["supported", "partially_supported", "unsupported"]


DECOMPOSE = """Break the answer into individual factual claims.
Each claim must stand alone and contain one verifiable assertion.
Ignore hedging, pleasantries, and citation markers."""

JUDGE = """You check whether a claim is supported by the numbered passages.

Judge ONLY whether the passages support the claim. Do not use outside knowledge:
a true statement that is absent from the passages is "unsupported".

- supported: a passage states or directly entails the claim
- partially_supported: a passage relates but does not establish it
- unsupported: no passage supports it"""


class Judge:
    def __init__(self, model: str = JUDGE_MODEL):
        self.client = OpenAI()
        self.model = model

    def _parse(self, schema, system: str, user: str):
        completion = self.client.chat.completions.parse(
            model=self.model, temperature=0, max_completion_tokens=800,
            response_format=schema,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return completion.choices[0].message.parsed

    def faithfulness(self, answer: str, context: str) -> dict:
        """Fraction of the answer's claims that the context supports."""
        claims = self._parse(Claims, DECOMPOSE, f"Answer:\n{answer}").claims
        if not claims:
            return {"score": 0.0, "claims": [], "n": 0}

        verdicts = []
        for claim in claims:
            v = self._parse(
                ClaimVerdict, JUDGE, f"Passages:\n{context}\n\nClaim: {claim}"
            )
            verdicts.append({"claim": claim, "verdict": v.verdict,
                             "reasoning": v.reasoning})

        supported = sum(v["verdict"] == "supported" for v in verdicts)
        return {"score": supported / len(claims), "claims": verdicts, "n": len(claims)}

    def citation_accuracy(self, answer: str, numbered_passages: dict[int, str]) -> dict:
        """Does the passage cited as [n] actually support the sentence citing it?"""
        checks = []
        for sentence in re.split(r"(?<=[.!?])\s+", answer):
            for n in {int(m) for m in re.findall(r"\[(\d+)\]", sentence)}:
                passage = numbered_passages.get(n)
                if passage is None:
                    checks.append({"citation": n, "verdict": "unsupported",
                                   "reasoning": "cited a passage that was not provided"})
                    continue
                v = self._parse(
                    ClaimVerdict, JUDGE,
                    f"Passages:\n[{n}] {passage}\n\nClaim: {sentence}",
                )
                checks.append({"citation": n, "verdict": v.verdict,
                               "reasoning": v.reasoning})

        if not checks:
            return {"score": None, "checks": []}
        good = sum(c["verdict"] == "supported" for c in checks)
        return {"score": good / len(checks), "checks": checks}
```

### The six rules this code encodes

1. **Judge with a different, stronger model.** Models prefer their own output. Your generator
   is `gpt-5.4-nano`; the judge is not.
2. **Structured output**, so you never regex a verdict out of prose.
3. **Three-point scale, not 1–10.** LLMs cannot resolve a 6 from a 7; the extra granularity is
   noise that looks like signal.
4. **`reasoning` is the first field.** Models generate fields in order, so it reasons before
   committing. Reverse them and the reasoning becomes a post-hoc rationalisation.
5. **One claim at a time.** "Is this answer faithful?" gets you a vibe. Per-claim gets you a
   fraction *and* tells you which sentence failed.
6. **Validate the judge** — next.

### Validating the judge — the step that separates professional from amateur

**An unvalidated judge is a random number generator with good manners.**

Hand-label 30 claim/verdict pairs yourself. Run the judge on the same 30. Compute agreement,
corrected for chance:

```python
from sklearn.metrics import cohen_kappa_score


def validate(human: list[str], judge: list[str]) -> dict:
    """Cohen's kappa between your labels and the judge's."""
    agree = sum(h == j for h, j in zip(human, judge)) / len(human)
    return {"raw_agreement": agree,
            "cohens_kappa": float(cohen_kappa_score(human, judge)),
            "n": len(human)}
```

| kappa | Reading |
|---|---|
| > 0.8 | excellent |
| 0.6–0.8 | usable |
| < 0.6 | your judge measures something you did not define — fix the rubric |

Report it. *"Our faithfulness judge agrees with human labels at κ = 0.82 on a 30-example
validation set"* is the sentence that makes a technical buyer trust every other number in your
report. Almost nobody does this, and it costs one afternoon.

**This is also the argument against reaching for a framework here.** If a framework's judge
returns κ = 0.5, you cannot fix a rubric you do not control.

---

## Step 7 — `eval/run_generation.py`

```python
"""Faithfulness, citation accuracy, and refusal over the datasets."""

import time

from eval.common import EVAL_DIR, read_jsonl
from eval.judges import Judge
from RAG_pipeline import RAGPipeline


def numbered(chunks: list[dict]) -> tuple[str, dict[int, str]]:
    """Rebuild the numbering the generator showed the model."""
    passages = {i: c["content"] for i, c in enumerate(chunks, start=1)}
    joined = "\n\n".join(f"[{i}] {text}" for i, text in passages.items())
    return joined, passages


def main(golden: str, negatives: str) -> dict:
    pipeline, judge = RAGPipeline(), Judge()
    faith, cites, latencies = [], [], []

    for q in read_jsonl(EVAL_DIR / "dataset" / golden):
        start = time.perf_counter()
        result = pipeline.ask(q["question"])
        latencies.append((time.perf_counter() - start) * 1000)

        context, passages = numbered(result["chunks"])
        faith.append(judge.faithfulness(result["answer"], context)["score"])
        c = judge.citation_accuracy(result["answer"], passages)["score"]
        if c is not None:
            cites.append(c)

    false_refusals = sum(
        not pipeline.ask(q["question"]).get("answer_found", True)
        for q in read_jsonl(EVAL_DIR / "dataset" / golden)
    )

    negs = read_jsonl(EVAL_DIR / "dataset" / negatives)
    refused = sum(
        not pipeline.ask(q["question"]).get("answer_found", True) for q in negs
    )

    latencies.sort()
    scores = {
        "faithfulness": sum(faith) / len(faith),
        "citation_accuracy": sum(cites) / len(cites) if cites else None,
        "refusal_rate": refused / len(negs),
        "false_refusal_rate": false_refusals / len(faith),
        "p50_latency_ms": latencies[len(latencies) // 2],
        "p95_latency_ms": latencies[int(len(latencies) * 0.95)],
    }
    for name, value in scores.items():
        print(f"{name:22} {value}")
    pipeline.close()
    return scores
```

**Report p95, not just the mean.** Averages hide the tail users actually complain about.

The loop above calls `ask()` twice per golden question, which doubles cost — fine for
clarity while learning, but cache the results once you are running this often.

---

## Step 8 — The regression harness

A one-off report is a school project. **A harness you re-run on every change is an engineering
practice**, and it is the artifact clients keep paying for.

```python
"""Write one result file per run, and diff two of them."""

import json
from datetime import datetime, timezone

from eval.common import EVAL_DIR, git_sha
from source import CONFIG


def save(retrieval: dict, generation: dict, dataset: str, n: int) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "config": {
            "top_k": CONFIG.top_k,
            "candidate_k": CONFIG.candidate_k,
            "rrf_k": CONFIG.rrf_k,
            "fts_normalization": CONFIG.fts_normalization,
            "chunk_max_tokens": CONFIG.chunk_max_tokens,
            "embedding_model": CONFIG.embedding_model,
            "chat_model": CONFIG.chat_model,
        },
        "dataset": {"name": dataset, "n": n},
        "retrieval": retrieval,
        "generation": generation,
    }
    path = EVAL_DIR / "results" / f"{datetime.now():%Y-%m-%dT%H%M}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("wrote", path)


def compare(old_path: str, new_path: str) -> None:
    old = json.loads(open(old_path).read())
    new = json.loads(open(new_path).read())

    print("config changes:")
    for key in new["config"]:
        if old["config"].get(key) != new["config"][key]:
            print(f"  {key}: {old['config'].get(key)} -> {new['config'][key]}")

    print("\nmetric changes:")
    for section in ("retrieval", "generation"):
        for metric, value in _flatten(new[section]).items():
            before = _flatten(old[section]).get(metric)
            if isinstance(value, (int, float)) and isinstance(before, (int, float)):
                delta = value - before
                flag = "  <-- regression" if delta < -0.02 else ""
                print(f"  {metric:28} {before:.3f} -> {value:.3f} ({delta:+.3f}){flag}")


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out
```

Recording `config` and `git_sha` is what makes runs comparable six months later. Then you can
state plainly: *"raising `candidate_k` to 100 gained 1.2 points of Recall@10 and cost 40ms of
p95 latency."* That sentence is the product.

---

## Step 9 — Experiments worth running

With the harness in place, each is one command.

```bash
uv run python -m eval.run_retrieval --k 3
uv run python -m eval.run_retrieval --k 10
uv run python -m eval.run_retrieval --k 20
```

| Experiment | Question it answers | How |
|---|---|---|
| dense vs sparse vs hybrid | Does fusion earn its complexity? | Step 4, already built |
| `top_k` sweep 3/5/10/20 | Smallest context that keeps recall | `--k` |
| `candidate_k` 20/50/100 | Is over-fetching paying off? | edit `CONFIG`, re-run |
| `rrf_k` 10/60/200 | How sensitive is fusion to its constant? | edit `CONFIG` |
| `fts_normalization` 0 vs 1 | Was the length-normalisation choice right? | edit `CONFIG` |
| chat model tiers | What does a bigger model buy? | `CONFIG.chat_model` |
| **chunk size 256/512/1024** | **Usually the biggest single lever** | requires re-ingest — costs embedding calls **and invalidates `chunk_key` labels** |

Chunk size is last because it is expensive and because it breaks your dataset labels — chunk
boundaries move, so `::12` no longer means the same passage. If you run it, re-verify labels
against the new chunking.

---

## What to hand a client

1. **The headline table** — dense vs sparse vs hybrid, with the bootstrap significance column.
2. **The `top_k` recall curve**, justifying the chosen value on cost grounds.
3. **Faithfulness and citation accuracy**, with the judge's kappa against human labels.
4. **Refusal and false-refusal rates**, together.
5. **Cost and p95 latency** per configuration.
6. **A failure gallery** — five real questions the system got wrong, each diagnosed as
   retrieval failure or generation failure.

Point 6 lands harder than the other five combined. Showing your own failures with an accurate
diagnosis is the strongest possible evidence that the rest of your numbers are honest.

---

## Pitfalls

| Pitfall | Why it hurts |
|---|---|
| Chunk ids as labels | Ids change on re-ingest; the dataset silently rots |
| Generated questions without paraphrase | Inflates keyword search; real users behave differently |
| Tuning on the test set | Your reported number is optimistic by an unknown amount |
| Reporting a 3-point gain on 50 questions | Inside the confidence interval — it is noise |
| Unvalidated LLM judge | Confident numbers measuring something you did not define |
| 1–10 rating scales | LLMs cannot resolve that finely |
| Only testing answerable questions | Misses the failure mode that reaches production |
| Averages without p95 | Hides the latency users complain about |
| Judging with the generator model | Self-preference bias inflates every score |

---

## Reference

- [Cormack et al., *Reciprocal Rank Fusion* (SIGIR 2009)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — the fusion method and where `k = 60` comes from
- [Järvelin & Kekäläinen, *Cumulated gain-based evaluation of IR techniques*](https://dl.acm.org/doi/10.1145/582415.582418) — the nDCG paper
- [`pytrec_eval`](https://github.com/cvangysel/pytrec_eval) — the implementation `beir` wraps
- [Liu et al., *Lost in the Middle*](https://arxiv.org/abs/2307.03172) — why passage position inside the context matters
- [Ragas](https://github.com/explodinggradients/ragas) — worth running as a cross-check once your own numbers exist
