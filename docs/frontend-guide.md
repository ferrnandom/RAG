# Building a Frontend Layer for AI Applications

A practical, transferable guide — written against this RAG API, designed to generalise to
every AI application you build afterwards.

---

## How to read this document

This is not a "copy this template" guide. Frontend work for AI applications is a small,
learnable set of ideas repeated forever, wrapped in an ecosystem that is much noisier than it
needs to be. The goal here is to give you the ideas, in the order that makes them stick, with
working code for **this** backend so nothing stays abstract.

The arc:

| Part | What you get |
|---|---|
| [1](#1-the-mental-model) | The mental model — the only three layers that exist |
| [2](#2-choosing-a-stack) | An honest stack decision, with the alternatives you'll be tempted by |
| [3](#3-the-minimum-javascript-you-actually-need) | The minimum JavaScript you actually need |
| [4](#4-stage-zero-one-html-file) | Stage zero: one HTML file that talks to your API today |
| [5](#5-backend-changes-you-must-make-first) | Backend changes this repo needs before a browser can call it |
| [6](#6-stage-one-the-real-frontend) | Stage one: the real frontend (React + Vite + TypeScript) |
| [7](#7-streaming-the-upgrade-that-changes-how-it-feels) | Streaming — the upgrade that changes how the app *feels* |
| [8](#8-rendering-answers-and-citations-safely) | Rendering answers and citations safely |
| [9](#9-the-polish-that-separates-a-demo-from-a-product) | The polish that separates a demo from a product |
| [10](#10-shipping-it) | Shipping it — one server, no CORS, one URL |
| [11](#11-the-transferable-pattern) | The transferable pattern for your next AI app |
| [12](#12-learning-path) | A learning path with honest time estimates |
| [A](#appendix-a-error-cookbook) / [B](#appendix-b-glossary) | Error cookbook and glossary |

If you only read two sections, read [§1](#1-the-mental-model) and [§6.3](#63-the-idea-that-carries-everything-request-state-as-a-union).

---

## 1. The mental model

A frontend for an AI application is three layers, and confusion almost always comes from
mixing them up. Keep them in separate files and most of the difficulty evaporates.

```
┌──────────────────────────────────────────────────────────────┐
│  PRESENTATION   What the user sees.                          │
│                 Components, CSS, layout, loading skeletons.  │
│                 Knows nothing about HTTP.                    │
├──────────────────────────────────────────────────────────────┤
│  STATE          What is true right now.                      │
│                 idle / loading / success / error, the query, │
│                 the answer, which citation is open.          │
│                 Knows nothing about CSS.                     │
├──────────────────────────────────────────────────────────────┤
│  TRANSPORT      How bytes get here.                          │
│                 fetch(), JSON parsing, error mapping,        │
│                 cancellation, streaming.                     │
│                 Knows nothing about React.                   │
└──────────────────────────────────────────────────────────────┘
```

### Why AI frontends are their own genre

A CRUD frontend does request → response in 50 ms and the user never notices the gap. An AI
frontend has properties that make the naive approach fall apart:

1. **Requests take seconds, not milliseconds.** Your `/answer` endpoint does an embedding
   call, two Postgres queries, and a chat completion. Three to fifteen seconds is normal. The
   UI must be honest about waiting, or users click the button four times.
2. **The user can out-type the network.** Ask a question, change your mind, ask another. Now
   two requests are in flight and the *first* one may land last, overwriting the newer answer
   with a stale one. This is the single most common real bug in AI frontends. The fix is
   cancellation ([§6.4](#64-transport-a-typed-api-client)).
3. **The output is unstructured text that must be trusted carefully.** A model's answer is
   Markdown-ish text from a probabilistic process. Rendering it as raw HTML is a genuine
   security hole ([§8](#8-rendering-answers-and-citations-safely)).
4. **Failure is normal, not exceptional.** Rate limits, timeouts, an empty retrieval, a
   refusal. Your error state is a first-class screen, not an afterthought `alert()`.
5. **Progressive output beats fast output.** A streamed answer that takes 8 seconds feels
   faster than a blocking one that takes 4. This is perception, not throughput, and it is the
   highest-leverage change you can make ([§7](#7-streaming-the-upgrade-that-changes-how-it-feels)).

Every one of those is a frontend concern. None of them is about CSS. That is why "learning
frontend" for AI apps is mostly learning **asynchronous state management**, and why this guide
spends more time there than on styling.

### Where the frontend sits in your architecture

```
Browser (React)  ──HTTP/JSON──▶  FastAPI (main.py)  ──▶  RAGPipeline
                                        │                    ├─▶ Postgres + pgvector
       no API keys here ────────────────┘                    └─▶ OpenAI
       ever
```

Your existing architecture is already correct for this, and that is worth understanding
rather than taking for granted. The browser talks only to *your* server. `OPENAI_API_KEY`
lives in `.env` on the server and is never sent to a client. Anything shipped to a browser is
readable by anyone who opens DevTools — bundlers do not hide secrets, they only minify them.

> **Rule with no exceptions:** if a key can spend money or read private data, it never
> crosses into browser code. When a tutorial shows `new OpenAI({ apiKey, dangerouslyAllowBrowser: true })`,
> close the tab.

---

## 2. Choosing a stack

Four realistic options for putting a UI on a Python AI service. All of them work. They differ
in what you learn and what you can do afterwards.

| Option | Time to first UI | Ceiling | What you learn |
|---|---|---|---|
| **Streamlit / Gradio** | 30 minutes | Low — fights you on custom layout, streaming, citations | Nothing transferable |
| **Plain HTML + vanilla JS** | 1 hour | Medium — fine up to ~500 lines, then unmanageable | The fundamentals, honestly |
| **React + Vite + TypeScript** | Half a day | High — this is what production apps are | The industry standard |
| **Next.js** | A day | Highest — SSR, routing, server-side secrets, auth | React *plus* a framework's opinions |

### The recommendation

**Do stage zero in plain HTML ([§4](#4-stage-zero-one-html-file)), then build the real thing in React + Vite + TypeScript ([§6](#6-stage-one-the-real-frontend)).**

The reasoning, since you asked to *learn* rather than to ship the fastest possible thing:

- **Streamlit is a trap for your stated goal.** It is genuinely excellent for internal demos
  and I would use it to show a colleague a retrieval experiment. But it is a Python DSL that
  renders a fixed widget vocabulary. You will not learn HTTP, state, or rendering, and the
  first time you want a citation chip that opens a passage drawer, you will be writing custom
  components anyway — in React, without having learned React. Keep it in your pocket for
  throwaway tools; it is not the layer you asked for.
- **React is the transferable skill.** Not because it is technically superior to Vue or
  Svelte — it isn't, particularly — but because it is what job listings, documentation,
  component libraries, and the entire AI-tooling ecosystem assume. Vercel's AI SDK,
  `assistant-ui`, CopilotKit, every chat template: React. Learning it means the ecosystem
  works *for* you.
- **Vite over Next.js, for now.** Next.js is a great framework carrying a lot of concepts —
  server components, the app router, two rendering models — that solve problems you do not
  have. You already have a backend; you need a client for it. Vite is a dev server and a
  bundler and nothing else. Move to Next.js the day you need server-side rendering, real
  auth, or you want the frontend server to hold secrets.
- **TypeScript from day one, not day thirty.** This is the least popular advice here and the
  one I would defend hardest. Your API returns a specific shape. TypeScript turns
  `answer.source` (wrong — the field is `sources`) into a red squiggle in your editor instead
  of `undefined` rendering as a blank panel at 11pm. For someone learning, types are
  documentation that cannot go stale. The cost is roughly one afternoon of annoyance.

**Styling:** plain CSS with custom properties, as shown in this guide. Not Tailwind — not
because Tailwind is bad (it's very good, and it's what I'd use on a team) but because learning
component architecture and a styling DSL simultaneously means you learn neither. Add Tailwind
once React feels boring.

**Component libraries:** skip them for the first app. `shadcn/ui` is the right answer later.
Build the button yourself once so you know what a library is doing for you.

---

## 3. The minimum JavaScript you actually need

You do not need to "learn JavaScript" before starting. You need about eight things. Here they
are, each with the shape you'll actually type.

**1. `const` / `let`, arrow functions, template literals**

```js
const topK = 10;
const double = (n) => n * 2;
const url = `${BASE}/answer`;          // backticks, not quotes
```

**2. Objects and arrays, destructuring**

```js
const { answer, sources } = response;       // pull fields out by name
const [first, ...rest] = sources;           // pull items out by position
```

**3. `map` and `filter` — the loop you'll use 90% of the time**

```js
sources.map((s) => `[${s.citation}] ${s.source}`)   // transform every item
sources.filter((s) => s.page_numbers.length > 0)    // keep some items
```

React renders lists with `map`. If `map` is comfortable, React lists are comfortable.

**4. Spread, for immutable updates**

```js
const updated = { ...state, status: "loading" };    // copy, with one field changed
const appended = [...messages, newMessage];         // copy, with one item added
```

React only re-renders when it sees a *new* object. Mutating in place (`state.status = "loading"`)
changes nothing on screen. This trips up everyone once.

**5. Optional chaining and nullish coalescing**

```js
const pages = source?.page_numbers ?? [];   // don't crash if source is undefined
```

**6. Promises and `async` / `await`**

```js
async function ask(query) {
  const res = await fetch(url, { ... });   // "pause here until the response arrives"
  const data = await res.json();           // "…and until the body is parsed"
  return data;
}
```

`await` only works inside `async` functions. An `async` function always returns a Promise,
which is why calling it from a click handler does not block the page.

**7. `try` / `catch` / `finally`**

```js
try {
  const data = await ask(query);
} catch (err) {
  setError(String(err));
} finally {
  setLoading(false);          // runs whether or not it threw
}
```

**8. JSON**

`JSON.stringify(obj)` on the way out, `res.json()` on the way in. Your FastAPI models
(`Query`, `Answer`, `Source`) are the contract on the other side.

That is genuinely the list. Everything else — classes, generators, prototypes, `this` — you
can learn later or never.

---

## 4. Stage zero: one HTML file

Before any tooling, prove the loop end to end. This file has no build step, no `npm`, no
dependencies. Save it, open it in a browser, and you have a working UI for your RAG system.

Its purpose is pedagogical: it is small enough to hold in your head, and every concept in the
React version appears here in its simplest form.

**`web/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RAG — stage zero</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 46rem; margin: 3rem auto;
           padding: 0 1rem; line-height: 1.6; }
    form { display: flex; gap: .5rem; }
    input { flex: 1; padding: .6rem .8rem; font: inherit;
            border: 1px solid #ccc; border-radius: 6px; }
    button { padding: .6rem 1.2rem; font: inherit; cursor: pointer;
             border: 0; border-radius: 6px; background: #1a1a1a; color: white; }
    button[disabled] { opacity: .5; cursor: not-allowed; }
    #answer { white-space: pre-wrap; margin-top: 2rem; }
    .source { font-size: .875rem; color: #555; }
    .error { color: #b00020; }
  </style>
</head>
<body>
  <h1>Ask the documents</h1>

  <form id="form">
    <input id="q" placeholder="How does backpropagation compute gradients?" required />
    <button id="btn" type="submit">Ask</button>
  </form>

  <div id="answer"></div>
  <div id="sources"></div>

  <script>
    const API = "http://127.0.0.1:8000";

    const form    = document.getElementById("form");
    const input   = document.getElementById("q");
    const button  = document.getElementById("btn");
    const answer  = document.getElementById("answer");
    const sources = document.getElementById("sources");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();              // stop the browser reloading the page

      // --- enter the loading state ---
      button.disabled = true;
      button.textContent = "Thinking…";
      answer.textContent = "";
      answer.className = "";
      sources.innerHTML = "";

      try {
        const res = await fetch(`${API}/answer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: input.value }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();

        // --- success state ---
        answer.textContent = data.answer;
        sources.innerHTML = data.sources
          .map((s) => `<div class="source">[${s.citation}] ${s.source}
                       — pages ${s.page_numbers.join(", ") || "n/a"}</div>`)
          .join("");
      } catch (err) {
        // --- error state ---
        answer.className = "error";
        answer.textContent = `Request failed: ${err.message}`;
      } finally {
        // --- always leave the loading state ---
        button.disabled = false;
        button.textContent = "Ask";
      }
    });
  </script>
</body>
</html>
```

Read the comments in the `submit` handler. That four-phase shape — **enter loading → success
→ error → always leave loading** — is the entire job. Everything in [§6](#6-stage-one-the-real-frontend) is that same
shape, made reusable and type-safe.

**When you open this file, it will fail.** The browser console will say something about CORS.
That is expected, and it is the subject of the next section.

---

## 5. Backend changes you must make first

Three changes to `main.py`. The first is mandatory; the other two make the frontend
meaningfully better and are cheap.

### 5.1 CORS — mandatory

A browser refuses to let a page on `http://localhost:5173` read a response from
`http://127.0.0.1:8000`. Different port means different **origin**, and the same-origin policy
blocks it unless the server explicitly opts in. This is a browser rule, not a network one —
which is why `curl`, `requests`, and `execute_api.py` all work fine while the browser does not.

The error in DevTools reads:

```
Access to fetch at 'http://127.0.0.1:8000/answer' from origin 'http://localhost:5173'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

The fix, in `main.py`, immediately after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # vite dev server
        "http://127.0.0.1:5173",   # same server, other spelling — browsers treat these as different origins
        "http://localhost:8000",   # the built frontend, served by this app (see §10)
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

Two notes worth internalising:

- `localhost` and `127.0.0.1` are **different origins** to a browser even though they are the
  same machine. Listing both saves an hour of confusion.
- `allow_origins=["*"]` works and is acceptable while your API is unauthenticated and local.
  The moment you add cookies or auth, it becomes wrong — and `allow_credentials=True`
  combined with `"*"` is rejected outright by the spec. Start explicit; you'll never have to
  remember to tighten it.

CORS adds no new dependency: `CORSMiddleware` ships with FastAPI (via Starlette).

### 5.2 Return the retrieved chunks — recommended

Right now `/answer` is declared `response_model=Answer`, and `Answer` has three fields:
`answer`, `sources`, `model`. FastAPI filters the response to exactly the declared model, so
even though `RAGPipeline.ask` puts the full `chunks` list into its return value, **the browser
never receives it**. The frontend can show *that* citation [1] is `Lecture-08_26.pdf` page 4,
but cannot show the passage the model actually read.

For a RAG interface that is the wrong trade. The passage is the proof. Showing it is what
makes the system inspectable instead of a black box — and inspectability is most of the value
of building RAG rather than calling a chatbot.

Add a chunk model and one field:

```python
class Chunk(BaseModel):
    id: int
    content: str
    metadata: dict[str, Any] = {}
    rank: int
    rrf_score: float


class Answer(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    chunks: list[Chunk] = []          # ← new
```

No change to `RAGPipeline.ask` is needed — it already returns `chunks`; the response model was
simply discarding it.

> **The cost:** ten chunks of ~512 tokens is roughly 20 KB of JSON per answer. On localhost
> that is free. Over a real network it is still fine, but if you later add a `/answer`
> variant for mobile, make chunk inclusion a request flag rather than always-on.

### 5.3 A stable error shape — recommended

Your handlers raise `HTTPException(status_code=502, detail=f"generation failed: {e}")`, which
FastAPI serialises as `{"detail": "generation failed: …"}`. Good. But **validation** errors
(422, e.g. an empty query violating `min_length=1`) return `detail` as an *array of objects*:

```json
{"detail": [{"type": "string_too_short", "loc": ["body", "query"], "msg": "..."}]}
```

If your frontend does `throw new Error(body.detail)` it will render the string
`"[object Object]"` to the user. Handle both shapes in the client — [§6.4](#64-transport-a-typed-api-client) does exactly that.
This is a small thing that shows up in every FastAPI + React project ever built.

---

## 6. Stage one: the real frontend

### 6.1 Project setup

You need Node.js 20 or newer (`node --version`). Then, from the repository root:

```bash
npm create vite@latest web -- --template react-ts
cd web
npm install
npm run dev
```

`npm create vite` scaffolds the project; `--template react-ts` selects React with TypeScript.
The dev server starts on `http://localhost:5173` with hot module replacement — save a file,
the browser updates in ~50 ms without losing your typed-in query.

That speed is worth noting given your backend's constraints: `import source` takes ~10 seconds
because of docling, so `fastapi dev` reloads are slow. The frontend loop is not. You will do
most of your UI iteration without restarting Python at all.

Add `web/node_modules` and `web/dist` to `.gitignore`.

**The file layout to aim for** (delete the scaffold's demo files):

```
web/
├─ index.html            # the single HTML page; Vite injects the bundle
├─ package.json
├─ tsconfig.json
├─ vite.config.ts
└─ src/
   ├─ main.tsx           # entry point: mounts React into index.html
   ├─ App.tsx            # composition + state — the only stateful component
   ├─ api.ts             # TRANSPORT layer: types + fetch wrappers
   ├─ styles.css
   └─ components/
      ├─ QueryForm.tsx
      ├─ AnswerPanel.tsx
      ├─ SourceList.tsx
      └─ ChunkDrawer.tsx
```

The rule that keeps this maintainable: **`api.ts` never imports React; components never call
`fetch`.** Enforce it and the codebase stays comprehensible at ten times this size.

### 6.2 What React actually is, in four sentences

You write functions that return HTML-looking markup (JSX). React calls those functions and
puts the result on screen. When state changes, React calls the affected functions again and
updates only the parts of the DOM that differ. That is the whole model — **UI is a function
of state**.

```tsx
function Greeting({ name }: { name: string }) {   // props: inputs from the parent
  const [count, setCount] = useState(0);           // state: memory that survives re-renders
  return (
    <button onClick={() => setCount(count + 1)}>
      {name} clicked {count} times
    </button>
  );
}
```

- **Props** flow down from parent to child. Read-only.
- **State** (`useState`) belongs to a component. Calling the setter schedules a re-render.
- **`{ }`** in JSX means "evaluate this JavaScript expression here".
- `className`, not `class` (`class` is a reserved word in JavaScript).

Skip `useEffect` for now. It is the most misused hook in React, and a request fired from a
button click does not need it. You need it for things that must happen *when the component
appears* — like the health check in [§9](#9-the-polish-that-separates-a-demo-from-a-product) — and rarely elsewhere.

### 6.3 The idea that carries everything: request state as a union

Here is the mistake nearly every tutorial makes:

```tsx
const [loading, setLoading] = useState(false);
const [data, setData]       = useState(null);
const [error, setError]     = useState(null);
```

Three independent booleans and nullables describe **eight** combinations, of which only four
are real. Nothing stops `loading === true` alongside a stale `data` and a leftover `error`.
Every "why is the spinner showing under the answer" bug lives in that gap.

Model it as one value with four possible shapes instead:

```ts
export type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string };
```

This is a **discriminated union**, and it is the highest-value TypeScript concept for AI
frontends. Impossible states become unrepresentable: there is no way to be loading *and* have
data, because the `loading` shape has no `data` field. TypeScript then forces you to handle
every case at the point of rendering:

```tsx
switch (state.status) {
  case "idle":    return <EmptyState />;
  case "loading": return <Skeleton />;
  case "success": return <AnswerPanel result={state.data} />;   // .data exists here, guaranteed
  case "error":   return <ErrorBanner message={state.message} />;
}
```

Inside `case "success"`, `state.data` is typed and non-null. Inside `case "loading"`, touching
`state.data` is a compile error. You get correct rendering by construction rather than by
remembering.

Learn this once and you will use it in every asynchronous UI you ever write, in any framework.

### 6.4 Transport: a typed API client

**`web/src/api.ts`** — the only file that knows HTTP exists.

```ts
const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

/* ---------- Types: mirror the Pydantic models in main.py ---------- */

export interface Source {
  citation: number;
  id: number | null;
  source: string;
  page_numbers: number[];
  headings: string[];
}

export interface Chunk {
  id: number;
  content: string;
  metadata: {
    source?: string;
    page_numbers?: number[];
    headings?: string[];
    chunk_index?: number;
    total_chunks?: number;
  };
  rank: number;
  rrf_score: number;
}

export interface AnswerResponse {
  answer: string;
  sources: Source[];
  model: string;
  chunks: Chunk[];        // requires the §5.2 backend change
}

export interface HealthResponse {
  status: string;
  chunks: number;
}

/* ---------- Error handling ---------- */

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/** Turn FastAPI's two different `detail` shapes into one readable string. */
async function toError(res: Response): Promise<ApiError> {
  let message = `Request failed (HTTP ${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      message = body.detail;                                  // HTTPException
    } else if (Array.isArray(body.detail)) {
      message = body.detail                                   // 422 validation
        .map((d: { loc?: string[]; msg?: string }) =>
          `${d.loc?.slice(1).join(".") ?? "input"}: ${d.msg}`)
        .join("; ");
    }
  } catch {
    /* body was not JSON — keep the generic message */
  }
  return new ApiError(message, res.status);
}

/* ---------- Endpoints ---------- */

export async function ask(
  query: string,
  topK?: number,
  signal?: AbortSignal,
): Promise<AnswerResponse> {
  const res = await fetch(`${BASE}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK ?? null }),
    signal,
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function search(
  query: string,
  topK?: number,
  signal?: AbortSignal,
): Promise<Chunk[]> {
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK ?? null }),
    signal,
  });
  if (!res.ok) throw await toError(res);
  return res.json();
}

export async function health(): Promise<HealthResponse> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw await toError(res);
  return res.json();
}
```

Four things here are deliberate and worth copying into your next project:

1. **`BASE` comes from an environment variable with a sane fallback.** Vite exposes any
   variable prefixed `VITE_` as `import.meta.env.VITE_*`. In development it points at
   `127.0.0.1:8000`; in production ([§10](#10-shipping-it)) you set `VITE_API_URL=""` so requests go to the
   same origin that served the page, and CORS stops being your problem forever.
2. **`res.ok` is checked explicitly.** `fetch` does **not** throw on 4xx or 5xx — it only
   rejects on network failure. A 502 arrives as a perfectly successful Promise. Forgetting
   this check is the most common `fetch` bug in existence.
3. **`signal` is threaded through.** This enables cancellation, which is how you fix the
   stale-response race from [§1](#1-the-mental-model).
4. **`top_k: topK ?? null`.** Your `Query` model declares `top_k: int | None`, so `null` is
   valid and means "use `CONFIG.top_k`". Sending `undefined` would drop the key entirely —
   also fine here, but being explicit documents the intent.

### 6.5 State: one hook, reused everywhere

**`web/src/useAsk.ts`**

```ts
import { useCallback, useRef, useState } from "react";
import { ask, ApiError, type AnswerResponse } from "./api";

export type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; message: string };

export function useAsk() {
  const [state, setState] = useState<RequestState<AnswerResponse>>({ status: "idle" });
  const inflight = useRef<AbortController | null>(null);

  const run = useCallback(async (query: string, topK?: number) => {
    inflight.current?.abort();                 // cancel the previous request, if any
    const controller = new AbortController();
    inflight.current = controller;

    setState({ status: "loading" });
    try {
      const data = await ask(query, topK, controller.signal);
      if (controller.signal.aborted) return;   // superseded while awaiting — drop the result
      setState({ status: "success", data });
    } catch (err) {
      if (controller.signal.aborted) return;   // an abort is not an error the user should see
      setState({
        status: "error",
        message: err instanceof ApiError ? err.message : "Could not reach the API. Is it running?",
      });
    }
  }, []);

  const reset = useCallback(() => {
    inflight.current?.abort();
    setState({ status: "idle" });
  }, []);

  return { state, run, reset };
}
```

A **custom hook** is just a function whose name starts with `use` and which calls other hooks.
That naming convention is not decoration — React's linter uses it to check the rules of hooks.

The `AbortController` block is what makes this production-grade rather than tutorial-grade.
Trace the scenario:

```
t=0.0  user asks "what is AdamW"       → request A starts, state = loading
t=1.2  user asks "what is dropout"     → A.abort(), request B starts
t=4.0  B resolves                      → state = success(dropout answer)   ✓
t=6.5  A would have resolved           → aborted; fetch rejected at t=1.2, guard returns
```

Without cancellation, at t=6.5 the AdamW answer overwrites the dropout answer on screen and
the user sees a reply to a question they abandoned. It is unreproducible on a fast localhost
and constant on a real network — which is exactly why it reaches production so often.

### 6.6 Presentation: the components

**`web/src/App.tsx`** — composition and the only state ownership.

```tsx
import { useState } from "react";
import { useAsk } from "./useAsk";
import { QueryForm } from "./components/QueryForm";
import { AnswerPanel } from "./components/AnswerPanel";
import { ChunkDrawer } from "./components/ChunkDrawer";
import type { Chunk } from "./api";
import "./styles.css";

export default function App() {
  const { state, run } = useAsk();
  const [openChunk, setOpenChunk] = useState<Chunk | null>(null);

  return (
    <div className="app">
      <header>
        <h1>Document Assistant</h1>
        <p className="subtitle">Hybrid retrieval over the indexed PDF corpus</p>
      </header>

      <QueryForm onSubmit={run} busy={state.status === "loading"} />

      <main>
        {state.status === "idle" && (
          <p className="hint">
            Ask a question about the indexed documents. Answers cite the passages they came from.
          </p>
        )}

        {state.status === "loading" && (
          <div className="skeleton" role="status" aria-live="polite">
            <span className="sr-only">Searching and generating an answer…</span>
            <div className="bar" /><div className="bar" /><div className="bar short" />
          </div>
        )}

        {state.status === "error" && (
          <div className="error" role="alert">
            <strong>Something went wrong.</strong>
            <p>{state.message}</p>
          </div>
        )}

        {state.status === "success" && (
          <AnswerPanel
            result={state.data}
            onCitationClick={(n) =>
              setOpenChunk(state.data.chunks.find((c) => c.rank === n) ?? null)
            }
          />
        )}
      </main>

      {openChunk && <ChunkDrawer chunk={openChunk} onClose={() => setOpenChunk(null)} />}
    </div>
  );
}
```

Note where state lives. `App` owns it; children receive props and emit callbacks. This is
"lifting state up", and it is why you do not need Redux, Zustand, or any state library for an
app this size. Reach for one when prop-passing gets genuinely painful — usually four or more
levels deep — not before.

**`web/src/components/QueryForm.tsx`**

```tsx
import { useState } from "react";

interface Props {
  onSubmit: (query: string) => void;
  busy: boolean;
}

export function QueryForm({ onSubmit, busy }: Props) {
  const [value, setValue] = useState("");
  const trimmed = value.trim();

  return (
    <form
      className="query-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (trimmed) onSubmit(trimmed);
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="How does backpropagation compute gradients?"
        aria-label="Question"
        autoFocus
      />
      <button type="submit" disabled={busy || !trimmed}>
        {busy ? "Thinking…" : "Ask"}
      </button>
    </form>
  );
}
```

That `<input>` is a **controlled component**: React state is the source of truth, and the DOM
merely reflects it. `value` + `onChange` always travel together — supply `value` without
`onChange` and the field appears frozen, which is a rite of passage.

`e.preventDefault()` stops the browser's default form submission (a full page reload). Forget
it and your app flashes and resets on every question.

**`web/src/components/AnswerPanel.tsx`**

```tsx
import type { AnswerResponse } from "../api";
import { SourceList } from "./SourceList";

interface Props {
  result: AnswerResponse;
  onCitationClick: (citation: number) => void;
}

/** Split the answer on [n] markers and turn each one into a clickable chip. */
function renderWithCitations(text: string, onClick: (n: number) => void) {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return <span key={i}>{part}</span>;
    const n = Number(match[1]);
    return (
      <button key={i} className="citation" onClick={() => onClick(n)}
              title={`Show passage ${n}`}>
        {n}
      </button>
    );
  });
}

export function AnswerPanel({ result, onCitationClick }: Props) {
  return (
    <article className="answer">
      <div className="answer-body">
        {renderWithCitations(result.answer, onCitationClick)}
      </div>
      <SourceList sources={result.sources} onSelect={onCitationClick} />
      <footer className="meta">Generated by {result.model}</footer>
    </article>
  );
}
```

This is where your project's specific contract pays off. `SYSTEM_PROMPT` in
[source/generate.py](../source/generate.py) instructs the model to cite with `[1]`, `[2]`, and
`_source()` numbers the sources with the same `enumerate(chunks, start=1)`. So citation `n`
corresponds to the chunk at `rank === n`. The regex splitter turns that convention into a
clickable interface at zero cost.

`key={i}` deserves a note: React needs a stable identity per list item to update efficiently.
Index is acceptable here because the list is regenerated wholesale and never reordered. For
lists that get inserted into or sorted, use a real ID (`key={chunk.id}`) — index keys in a
reorderable list cause genuinely baffling bugs.

**`web/src/components/SourceList.tsx`**

```tsx
import type { Source } from "../api";

export function SourceList({
  sources, onSelect,
}: { sources: Source[]; onSelect: (citation: number) => void }) {
  if (sources.length === 0) return null;

  return (
    <section className="sources">
      <h2>Sources</h2>
      <ol>
        {sources.map((s) => (
          <li key={s.citation}>
            <button className="source-row" onClick={() => onSelect(s.citation)}>
              <span className="source-name">{s.source}</span>
              {s.page_numbers.length > 0 && (
                <span className="pages">p. {s.page_numbers.join(", ")}</span>
              )}
              {s.headings.length > 0 && (
                <span className="headings">{s.headings.join(" › ")}</span>
              )}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
```

**`web/src/components/ChunkDrawer.tsx`** — the panel that shows the actual retrieved text.

```tsx
import type { Chunk } from "../api";

export function ChunkDrawer({ chunk, onClose }: { chunk: Chunk; onClose: () => void }) {
  return (
    <aside className="drawer" role="dialog" aria-label="Retrieved passage">
      <header>
        <strong>Passage {chunk.rank}</strong>
        <button onClick={onClose} aria-label="Close">×</button>
      </header>
      <p className="drawer-meta">
        {chunk.metadata.source?.split(/[\\/]/).pop()}
        {chunk.metadata.page_numbers?.length
          ? ` — p. ${chunk.metadata.page_numbers.join(", ")}` : ""}
        {" · "}RRF {chunk.rrf_score.toFixed(4)}
      </p>
      <pre className="drawer-body">{chunk.content}</pre>
    </aside>
  );
}
```

The `split(/[\\/]/).pop()` handles your Windows paths: `metadata["source"]` holds a full path
with backslashes (`C:\Users\...\data\Lecture-08_26.pdf`), which is deliberate — CLAUDE.md
documents that document identity depends on it being byte-identical. So the frontend strips
the directory for display and never mutates the stored value. Splitting on both separators
keeps this working if the corpus is ever ingested on Linux.

This drawer is, in my view, the single feature that makes a RAG UI worth building. Anyone can
show an answer. Showing the exact passage next to it, with its fusion score, is what lets you
tell "retrieval failed" from "the model fumbled a passage it had" — which is precisely the
distinction your Phase 3 evaluation work exists to measure.

### 6.7 Styling, briefly

**`web/src/styles.css`** — a starting point, not a design system.

```css
:root {
  --bg: #ffffff;
  --fg: #17171a;
  --muted: #6b6b76;
  --line: #e4e4e9;
  --accent: #2f5cff;
  --error: #b00020;
  --radius: 8px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #131316; --fg: #ececf1; --muted: #9a9aa8;
    --line: #2c2c33; --accent: #7d97ff;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.65;
}

.app { max-width: 48rem; margin: 0 auto; padding: 3rem 1.25rem 6rem; }
h1 { font-size: 1.5rem; margin: 0; }
.subtitle { color: var(--muted); margin: .25rem 0 2rem; }

.query-form { display: flex; gap: .5rem; }
.query-form input {
  flex: 1; padding: .7rem .9rem; font: inherit;
  background: var(--bg); color: var(--fg);
  border: 1px solid var(--line); border-radius: var(--radius);
}
.query-form input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.query-form button {
  padding: .7rem 1.4rem; font: inherit; font-weight: 600; cursor: pointer;
  border: 0; border-radius: var(--radius); background: var(--accent); color: white;
}
.query-form button:disabled { opacity: .45; cursor: not-allowed; }

.hint { color: var(--muted); margin-top: 2.5rem; }

.answer { margin-top: 2.5rem; }
.answer-body { white-space: pre-wrap; font-size: 1.05rem; }

.citation {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 1.25rem; height: 1.25rem; margin: 0 .1rem;
  font-size: .7rem; font-weight: 700; vertical-align: super;
  border: 0; border-radius: 999px; cursor: pointer;
  background: var(--accent); color: white;
}

.sources { margin-top: 2.5rem; border-top: 1px solid var(--line); padding-top: 1rem; }
.sources h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.sources ol { list-style: none; padding: 0; margin: .5rem 0 0; }
.source-row {
  display: flex; gap: .75rem; width: 100%; padding: .5rem 0;
  background: none; border: 0; color: inherit; font: inherit;
  text-align: left; cursor: pointer;
}
.source-row:hover .source-name { text-decoration: underline; }
.pages, .headings { color: var(--muted); font-size: .85rem; }

.meta { margin-top: 2rem; font-size: .8rem; color: var(--muted); }

.skeleton { margin-top: 2.5rem; }
.skeleton .bar {
  height: 1rem; margin-bottom: .6rem; border-radius: 4px;
  background: linear-gradient(90deg, var(--line) 25%, var(--bg) 50%, var(--line) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.skeleton .bar.short { width: 55%; }
@keyframes shimmer { to { background-position: -200% 0; } }
@media (prefers-reduced-motion: reduce) { .skeleton .bar { animation: none; } }

.error {
  margin-top: 2.5rem; padding: 1rem;
  border: 1px solid var(--error); border-radius: var(--radius); color: var(--error);
}

.drawer {
  position: fixed; inset: 0 0 0 auto; width: min(30rem, 100%);
  padding: 1.25rem; overflow-y: auto;
  background: var(--bg); border-left: 1px solid var(--line);
  box-shadow: -8px 0 24px rgb(0 0 0 / .12);
}
.drawer header { display: flex; justify-content: space-between; align-items: center; }
.drawer header button { background: none; border: 0; font-size: 1.5rem; cursor: pointer; color: var(--muted); }
.drawer-meta { color: var(--muted); font-size: .85rem; }
.drawer-body { white-space: pre-wrap; font-size: .9rem; font-family: inherit; }

.sr-only {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap;
}
```

Three CSS ideas carry most of the weight, and they are worth learning properly:

- **Custom properties** (`--bg`, used as `var(--bg)`) — one place to change a colour, and dark
  mode becomes a five-line media query.
- **Flexbox** — `display: flex` plus `gap` solves the large majority of layout. Learn
  `justify-content` and `align-items`; learn Grid later, when you have a real two-dimensional
  layout.
- **`prefers-color-scheme` and `prefers-reduced-motion`** — respecting system settings costs
  almost nothing and is what "professional" looks like from the outside.

---

## 7. Streaming: the upgrade that changes how it feels

A blocking `/answer` shows nothing for 3–15 seconds. Streaming shows the first words in about
a second. Same total time, completely different experience — and it removes the "is this
thing broken?" moment entirely.

### 7.1 The concept

Instead of one response body delivered at the end, the server keeps the connection open and
writes tokens as the model produces them. The browser reads the body incrementally.

The wire format is **Server-Sent Events** (SSE): a plain-text stream of `event:`/`data:` pairs
separated by blank lines.

```
event: sources
data: [{"citation":1,"source":"Lecture-08_26.pdf","page_numbers":[4]}]

event: token
data: {"t":"Back"}

event: token
data: {"t":"propagation"}

event: done
data: {}

```

Sending sources **first** is deliberate: retrieval finishes before generation starts, so you
can render the citation list while tokens are still arriving.

### 7.2 The backend

In `source/generate.py`, add a streaming sibling to `generate_answer`. Note that `_source` is
private; promote it to a public `sources()` method (keeping `_source` as an alias if you want
no churn) so `main.py` can call it without reaching into internals.

```python
from collections.abc import Iterator

    def generate_answer_stream(
        self, chunks: list[dict[str, Any]], query: str
    ) -> Iterator[str]:
        """Yield answer text incrementally. Mirrors generate_answer's prompt exactly."""
        if not chunks:
            yield "I found nothing relevant in the indexed documents for that question."
            return

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Context: {self._format_context(chunks)}\n\nQuestion: {query}"
                    ),
                },
            ],
            max_completion_tokens=CONFIG.max_answer_tokens,
            temperature=CONFIG.chat_temperature,
            stream=True,
        )
        for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta
```

And in `main.py`:

```python
import json
from fastapi.responses import StreamingResponse

@app.post("/answer/stream")
def answer_stream(request: Query):
    chunks = pipeline.search(request.query, request.top_k)
    generator = pipeline.answer_generator

    def events():
        yield f"event: sources\ndata: {json.dumps(generator.sources(chunks))}\n\n"
        try:
            for piece in generator.generate_answer_stream(chunks, request.query):
                yield f"event: token\ndata: {json.dumps({'t': piece})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
            return
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Four points that are easy to get wrong:

- **Keep the endpoint `def`, not `async def`.** CLAUDE.md's invariant holds here and the
  reason is worth stating precisely: FastAPI runs a `def` endpoint in a threadpool, and it
  also iterates a *synchronous* generator passed to `StreamingResponse` in a threadpool. Your
  blocking OpenAI client therefore never touches the event loop. Make it `async def` with the
  same blocking call inside and you freeze the loop for every other connected user.
- **`\n\n` terminates each event.** A single newline and the browser buffers forever waiting
  for the rest of the message.
- **Errors mid-stream cannot become an HTTP status.** The 200 response headers were sent
  before the first token. So failures become an `error` *event*, and the client must handle
  it. This surprises people the first time.
- **`X-Accel-Buffering: no`** tells nginx (if you deploy behind one) not to buffer the
  response. Without it, streaming works perfectly in development and delivers everything at
  once in production.

`response_model` cannot apply to a stream, so you lose FastAPI's automatic validation and
docs for this endpoint. Keep the blocking `/answer` alongside it — it stays the honest,
testable contract, and `execute_api.py` keeps working.

### 7.3 The client

**You cannot use `EventSource` here.** The browser's built-in SSE class only issues GET
requests with no body, and your endpoint is a POST carrying JSON. Use `fetch` and parse the
stream yourself — it is about twenty lines.

```ts
export interface StreamHandlers {
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

export async function askStream(
  query: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/answer/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });
  if (!res.ok || !res.body) throw await toError(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;

    // Events are separated by a blank line. The tail may be a partial event — keep it.
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const event = part.match(/^event: (.+)$/m)?.[1];
      const data  = part.match(/^data: (.+)$/m)?.[1];
      if (!event || !data) continue;

      const payload = JSON.parse(data);
      if (event === "sources")     handlers.onSources(payload);
      else if (event === "token")  handlers.onToken(payload.t);
      else if (event === "error")  handlers.onError(payload.message);
      else if (event === "done")   handlers.onDone();
    }
  }
}
```

The `buffer` handling is the part people skip and then debug for an hour. Network chunks do
not align with event boundaries — a single `read()` can deliver two and a half events. Keeping
the incomplete tail in `buffer` and prepending it to the next chunk is what makes the parser
correct rather than merely usually-correct.

Consuming it in a component:

```tsx
const [answer, setAnswer] = useState("");
const [sources, setSources] = useState<Source[]>([]);

async function handleAsk(query: string) {
  setAnswer("");
  setSources([]);
  await askStream(query, {
    onSources: setSources,
    onToken: (t) => setAnswer((prev) => prev + t),   // functional update — see below
    onError: (m) => setError(m),
    onDone: () => setBusy(false),
  });
}
```

`setAnswer((prev) => prev + t)` uses the **functional update** form, and it is mandatory here.
Writing `setAnswer(answer + t)` closes over the `answer` value from the render in which the
handler was created — with tokens arriving every few milliseconds you lose most of them. The
callback form always receives the latest state. This is one of the two or three genuinely
subtle things in React, and streaming is where it bites.

**Build the blocking version first.** Get [§6](#6-stage-one-the-real-frontend) working end to end, then add streaming as a
second path. Debugging JSX, CORS, and stream parsing simultaneously is not a good afternoon.

---

## 8. Rendering answers and citations safely

Model output is text you did not write, derived in part from documents you may not fully
control. Treat it as untrusted input.

### The rule

**Never pass model output to `dangerouslySetInnerHTML`.** React escapes strings by default —
`{answer}` renders `<script>` as visible characters, not as a script tag. That default is your
protection, and `dangerouslySetInnerHTML` is the one API that discards it. The name is a
warning, not a joke.

The `renderWithCitations` function in [§6.6](#66-presentation-the-components) is safe: it splits a string and returns React
elements containing strings. No HTML is ever parsed.

### When you want real Markdown

Your model emits headings, lists, and code blocks. `white-space: pre-wrap` shows them as raw
`##` and `-` characters, which looks unfinished. To render them properly:

```bash
npm install react-markdown remark-gfm
```

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

<ReactMarkdown
  remarkPlugins={[remarkGfm]}
  components={{
    // Keep citations clickable inside rendered Markdown
    p: ({ children }) => <p>{mapCitations(children, onCitationClick)}</p>,
  }}
>
  {result.answer}
</ReactMarkdown>
```

`react-markdown` parses to a React element tree and never touches `innerHTML`, so it is safe
by default. It does **not** allow raw HTML unless you explicitly add `rehype-raw` — do not add
`rehype-raw` to model output. If you ever must, put `rehype-sanitize` after it.

Making citations clickable *inside* rendered Markdown is fiddlier than the plain-text case,
because you must walk the children of each rendered node rather than splitting one string.
That is a good reason to ship the plain-text version first and treat Markdown as a later
refinement — the value is mostly cosmetic, while the citation interaction is the substance.

---

## 9. The polish that separates a demo from a product

Small, cheap, and disproportionately visible.

**Show system health on load.** Your `/health` endpoint returns the chunk count. Putting it in
the header tells the user (and you) that the API and database are alive before they type a
question. This is the legitimate use of `useEffect` — something that must happen when the
component appears, not in response to a click.

```tsx
const [chunks, setChunks] = useState<number | null>(null);

useEffect(() => {
  health().then((h) => setChunks(h.chunks)).catch(() => setChunks(null));
}, []);   // [] = run once, on mount

<span className="badge">
  {chunks === null ? "API offline" : `${chunks.toLocaleString()} chunks indexed`}
</span>
```

The empty dependency array is the whole API here: `[]` means run once; omitting it means run
after *every* render, which with a `setState` inside is an infinite loop. That loop is the
most common way a beginner accidentally spends money on API calls — worth knowing before you
point `useEffect` at `/answer`.

**Never leave the user staring at nothing.** Four screens: idle (with a suggestion), loading
(a skeleton, not a spinner — it hints at the shape of what's coming), success, error. Your
switch on `state.status` gives you all four for free.

**Make errors actionable.** "Could not reach the API. Is it running?" beats "Error". Map the
common cases: a `TypeError` from `fetch` means the server is down or CORS blocked it; 502
means generation failed; 503 means Postgres is unreachable — which, on this machine, most
often means the port-5433 binding problem documented in CLAUDE.md.

**Accessibility, the four that matter.** `aria-live="polite"` on the loading region so screen
readers announce it; `role="alert"` on errors; visible `:focus-visible` outlines (never
`outline: none` without a replacement); real `<button>` elements rather than clickable
`<div>`s, so keyboard and screen-reader users get them for free. That is most of the benefit
for very little work.

**Keyboard.** `Enter` submits (a `<form>` gives you that automatically — another reason not to
use a bare `<div>` with a click handler). `Escape` closes the drawer. `autoFocus` on the input.

**Disable the button while busy.** Already in `QueryForm` via `busy`. Without it, an impatient
user fires four `/answer` requests, each costing an embedding call and a completion.

---

## 10. Shipping it

### Development: two servers

```bash
uv run fastapi dev main.py     # terminal 1 — http://127.0.0.1:8000
npm --prefix web run dev       # terminal 2 — http://localhost:5173
```

Two origins, which is why [§5.1](#51-cors--mandatory) exists.

*Optional but pleasant:* Vite can proxy API calls so that even in development everything looks
same-origin, removing CORS from the picture entirely:

```ts
// web/vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/answer": "http://127.0.0.1:8000",
             "/search": "http://127.0.0.1:8000",
             "/health": "http://127.0.0.1:8000" },
  },
});
```

Then set `VITE_API_URL=""` and `fetch("/answer")` hits Vite, which forwards to FastAPI.
Configure CORS anyway — you will eventually call the API from somewhere else, and a
five-minute debugging session avoided is worth three lines of config.

### Production: one server, one URL

Build the frontend to static files and let FastAPI serve them. Same origin, no CORS, one
process, one port.

```bash
npm --prefix web run build     # → web/dist/  (index.html + hashed js/css)
```

Then, in `main.py`, **after every API route is declared**:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

DIST = Path(__file__).parent / "web" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
```

Three things about that snippet:

- **Mount order matters.** Routes are matched in declaration order, and a mount at `/` matches
  everything. Declare it last or it will swallow `/health`, `/search`, and `/answer`.
- **`html=True`** serves `index.html` for unmatched paths, which is what a single-page app
  needs if you later add client-side routing.
- **The `is_dir()` guard** keeps `uv run fastapi dev main.py` working before you have ever run
  a build. Without it, a missing directory raises at import time and the whole API fails to
  start.

Now `uv run fastapi dev main.py` alone serves the full application at
`http://127.0.0.1:8000`.

Rebuild after every frontend change — the `dist/` output is a snapshot, not a live view. For
day-to-day work keep using the Vite dev server; build only when you want to check the real
artefact.

**Deploying beyond localhost** is a separate topic, but the shape is: containerise the whole
thing (you already have `docker/` for Postgres), run `npm run build` in a Docker build stage,
copy `dist/` into the Python image, and serve with `uvicorn` behind a reverse proxy. The
frontend adds no new runtime dependency — it compiles to static files, and Node is needed only
at build time.

---

## 11. The transferable pattern

Everything above collapses to a checklist you can apply to any AI application you build. This
is the actual answer to "how do I add frontends to my AI apps".

**On the backend, before writing any UI:**

1. Enable CORS for your dev origin.
2. Return everything the UI needs in one response. Trace the screen you want and make sure
   each field exists — this is how [§5.2](#52-return-the-retrieved-chunks--recommended) was found.
3. Use a consistent error shape and meaningful status codes.
4. Add a `/health` endpoint. Free, and it makes the first five minutes of every debugging
   session shorter.
5. Stream if generation takes more than ~2 seconds.

**On the frontend, in this order:**

1. `api.ts` — types mirroring your server models, one function per endpoint, `signal` on each,
   errors normalised to strings. **No React in this file.**
2. A `RequestState<T>` union and one hook that owns it, with an `AbortController`.
3. Four render branches: idle, loading, success, error.
4. Presentational components that take props and emit callbacks, calling no APIs themselves.
5. Polish: disabled buttons while busy, actionable errors, focus states, `aria-live`.

**The reusable core across projects is three files:** `api.ts`, the `RequestState` union, and
the hook that owns it. The components change per application; that spine does not. A
summarisation tool, a classification dashboard, an agent chat UI — all of them are `POST` a
request, wait, render one of four states.

**What changes for a chat interface** (the most likely next thing you build): state becomes
`Message[]` rather than one answer, you append instead of replace, and you send prior turns
back with each request because HTTP is stateless and the model has no memory of its own. The
transport and state discipline are identical. Nothing in this guide is wasted.

---

## 12. Learning path

Honest estimates, assuming you already program comfortably in Python.

| Stage | Time | What to do |
|---|---|---|
| **1. Prove the loop** | 1–2 h | Build [§4](#4-stage-zero-one-html-file)'s HTML file, add CORS ([§5.1](#51-cors--mandatory)), get an answer on screen. Do not skip this — it makes everything later concrete. |
| **2. JavaScript gaps** | 3–4 h | [javascript.info](https://javascript.info) §2 (fundamentals) and §11 (promises/async). Only those. |
| **3. React fundamentals** | 4–6 h | [react.dev/learn](https://react.dev/learn) — "Describing the UI" and "Adding Interactivity". Stop before "Escape Hatches". |
| **4. Build stage one** | 6–10 h | [§6](#6-stage-one-the-real-frontend) of this guide, typing it rather than pasting. Break it deliberately and read the errors. |
| **5. TypeScript as needed** | ongoing | You already have most of it from Python type hints. Learn interfaces, unions, and generics when the compiler complains. |
| **6. Streaming** | 3–4 h | [§7](#7-streaming-the-upgrade-that-changes-how-it-feels). The highest-impact upgrade to how the app feels. |
| **7. CSS to a decent level** | ongoing | Flexbox first ([Flexbox Froggy](https://flexboxfroggy.com) is 30 minutes and genuinely works), custom properties second, Grid when you need it. |

**Roughly two focused weekends to competence.** You will not be a frontend engineer; you will
be someone who can put a credible, honest interface on any AI service they build, and who can
read a React codebase without flinching. That is the right target.

**Deliberately not on this list yet:** Redux, GraphQL, Next.js, Tailwind, testing libraries,
animation libraries, component frameworks. Every one is worth learning eventually and every
one is a distraction now. Add tooling when you feel the specific pain it removes — that is
also how you'll be able to tell whether it actually removed it.

**Sources worth trusting:** [react.dev](https://react.dev) (the official docs, rewritten in
2023 and genuinely excellent), [MDN](https://developer.mozilla.org) for anything web-platform
(`fetch`, CSS, SSE), [javascript.info](https://javascript.info) for the language. Be wary of
Medium tutorials and AI-app YouTube — a large fraction ship API keys to the browser, use
`useEffect` for click handlers, and skip cancellation entirely.

---

## Appendix A: Error cookbook

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: Failed to fetch`, DevTools mentions CORS | No `Access-Control-Allow-Origin` header | Add `CORSMiddleware` ([§5.1](#51-cors--mandatory)); list both `localhost` and `127.0.0.1` |
| `TypeError: Failed to fetch`, no CORS message | Server not running, or wrong port | Check `uv run fastapi dev main.py` and that `BASE` matches |
| 422 Unprocessable Entity | Body doesn't match `Query` — usually empty string or `top_k` out of `1..50` | Validate in the form; render `detail[].msg` ([§5.3](#53-a-stable-error-shape--recommended)) |
| 502 `generation failed` | OpenAI call raised — bad key, rate limit, wrong param | Read the server console; `max_completion_tokens`, not `max_tokens` |
| 503 `database unreachable` | Postgres down, or port 5433 blocked | `docker compose -f docker/docker-compose.yml up -d`; see CLAUDE.md on winnat |
| Answer renders `[object Object]` | Rendering a 422 `detail` array as a string | Normalise errors in `toError` |
| Old answer replaces the new one | Concurrent requests, no cancellation | `AbortController` ([§6.5](#65-state-one-hook-reused-everywhere)) |
| Streamed text loses most tokens | `setAnswer(answer + t)` closes over stale state | Functional update: `setAnswer(p => p + t)` |
| Stream arrives all at once | Missing `\n\n`, or a proxy buffering | Terminate events with a blank line; `X-Accel-Buffering: no` |
| Input appears frozen | `value` without `onChange` | Controlled inputs need both |
| Page reloads on submit | Missing `e.preventDefault()` | Add it to the form's `onSubmit` |
| Infinite re-render / runaway API calls | `useEffect` without a dependency array | Add `[]`, or the specific dependencies |
| Blank page after `npm run build` | Wrong asset base path | Set `base: "/"` in `vite.config.ts`; check the console |
| `/health` returns the SPA's HTML | `StaticFiles` mounted before the API routes | Move the mount below every route ([§10](#10-shipping-it)) |

## Appendix B: Glossary

| Term | Meaning |
|---|---|
| **Bundler** | Turns many source files into a few optimised browser files. Vite in dev; Rollup on build. |
| **Transpile** | Convert TypeScript/JSX into JavaScript a browser understands. |
| **HMR** | Hot Module Replacement — swaps changed code into the running page without a reload. |
| **SPA** | Single-Page Application: one HTML file; JavaScript renders everything after. |
| **Origin** | Scheme + host + port. `localhost:5173` ≠ `127.0.0.1:8000` ≠ `localhost:8000`. |
| **CORS** | Cross-Origin Resource Sharing — the server's opt-in to being called from another origin. |
| **SSE** | Server-Sent Events — one-way server→client text stream over plain HTTP. |
| **JSX** | HTML-like syntax inside JavaScript; compiles to function calls. |
| **Props** | Read-only inputs passed from a parent component to a child. |
| **State** | Data a component remembers across renders; changing it triggers a re-render. |
| **Hook** | A function starting with `use` that plugs into React's state/lifecycle. |
| **Controlled component** | A form input whose value is owned by React state. |
| **Discriminated union** | A type that is one of several shapes, distinguished by a literal tag field. |
| **AbortController** | Browser API for cancelling an in-flight `fetch`. |

---

## Appendix C: What this guide asks you to change in this repo

Collected in one place, so nothing gets lost:

| File | Change | Necessity |
|---|---|---|
| `main.py` | Add `CORSMiddleware` | Required — nothing works in a browser without it |
| `main.py` | Add `chunks` to the `Answer` response model | Recommended — enables the passage drawer, the feature that makes a RAG UI worth building |
| `main.py` | Mount `StaticFiles` after the routes | Only for single-origin production serving ([§10](#10-shipping-it)) |
| `main.py` | Add `POST /answer/stream` | Optional — do it after the blocking version works |
| `source/generate.py` | Add `generate_answer_stream`; promote `_source` to public `sources` | Only if streaming |
| `.gitignore` | Add `web/node_modules`, `web/dist` | Required once `web/` exists |

No new **Python** dependencies: `CORSMiddleware`, `StreamingResponse`, and `StaticFiles` all
ship with `fastapi[standard]`. That keeps invariant 7 in CLAUDE.md intact. The Node
dependencies live entirely under `web/` and are needed only at build time.

Two things in CLAUDE.md are worth reconciling before the frontend adds more surface area,
though neither blocks any of the above: the **195 orphaned chunks** would let this UI cite —
and now *display the full text of* — passages from PDFs that no longer exist on disk, which is
considerably more visible in a browser than in a terminal; and the "`requests` not declared"
defect is now stale, since `pyproject.toml:19` declares it.
