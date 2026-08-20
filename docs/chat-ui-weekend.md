# Weekend Project: A Chat UI That Looks Like Claude

A step-by-step guide to vibe-coding a clean, usable chat interface for your RAG system —
React + Vite + shadcn/ui — in one weekend.

Every step is spelled out, including the obvious ones. Nothing is assumed.

---

## What you are building

```
┌──────────────────────────────────────────────────────────┐
│  Document Assistant                    879 chunks  ☀/🌙  │  ← header
├──────────────────────────────────────────────────────────┤
│                                                          │
│                        ┌───────────────────────────────┐ │
│                        │ How does backprop compute     │ │  ← you (bubble)
│                        │ gradients?                    │ │
│                        └───────────────────────────────┘ │
│                                                          │
│   Backpropagation applies the chain rule backwards       │  ← assistant
│   through the network [1]. Each layer receives the       │    (no bubble,
│   gradient of the loss [2]…                              │     streams in)
│                                                          │
│   Sources                                                │  ← click → drawer
│     [1] Lecture-08_26.pdf · p. 4                         │    with the real
│     [2] Lecture-09_26.pdf · p. 11                        │    passage text
│                                                          │
├──────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────┐      │
│  │ Ask about your documents…                  [↑] │      │  ← composer
│  └────────────────────────────────────────────────┘      │    (grows as
└──────────────────────────────────────────────────────────┘     you type)
```

**How it feels:** text streams in word by word, the page never jumps, Enter sends,
Shift+Enter makes a new line, and it looks right in dark mode.

**One honest difference from Claude/ChatGPT:** every answer is grounded in *your* PDFs and
shows the exact passage it used. That is the entire point of the system you built, so the UI
puts it one click away.

---

## What this guide assumes

- You can copy and paste commands into a terminal.
- Your RAG system works today (`/answer` returns answers).
- You do **not** know React, CSS, or TypeScript. That is fine — you are directing an AI to
  write it, and reading just enough to stay in control.
- You have Claude Code open in this project.

**You do not need to memorise any code here.** The code blocks exist so you can see what
"correct" looks like, and so you can paste them back to me when something drifts.

---

## What you will NOT have on Sunday night

Stated up front so nothing feels broken when it is simply out of scope.

| Not included | Why |
|---|---|
| Conversations that survive a page refresh | Needs a database table and more API work |
| A sidebar of past conversations | Same reason. Half a day on its own |
| Login / multiple users | A weekend of its own, minimum |
| Deployment to the internet | Local only — Block 10 gets you one URL on your machine |
| A designed mobile layout | It will work on a phone; it will not be *designed* for one |

Follow-up questions that remember context ("what about the second one?") are an **optional
stretch** in [Block 11](#block-11-optional--real-conversation-memory). Everything before that
treats each question as independent, which is exactly what your API does today.

---

## How to vibe code well

Seven rules. These matter more than any code in this guide, and they transfer to every
project you ever direct an AI to build.

**1. Commit after every working checkpoint.** This is your undo button. Every time the guide
says *Checkpoint*, run:

```bash
git add -A && git commit -m "chat ui: <what you just got working>"
```

If the next step goes badly, `git reset --hard HEAD` puts you back to working. Vibe coding
without commits is the number one cause of "but it worked an hour ago."

**2. Describe what you SEE, not what you think the fix is.**

| Say this | Not this |
|---|---|
| "The send button sits below the text box instead of inside it on the right" | "Fix the flexbox on the composer" |
| "Text runs edge to edge with no gap" | "Add padding" |
| "The header scrolls away with the messages" | "Make the header position sticky" |

You know what looks wrong. I know which property causes it. Stay in your lane and the loop
runs twice as fast.

**3. One change per message.** "Make the bubbles rounder AND add dark mode AND fix the
scrolling" gets you three half-done things. Ask for one, look at it, commit, ask for the next.

**4. Screenshot when words fail.** Windows: `Win + Shift + S`, then paste straight into the
chat. One screenshot beats five sentences of description.

**5. Say "revert that" freely.** No explanation needed. If a change made things worse, say so
and we go back. This is a normal part of the process, not a failure.

**6. Paste the WHOLE error.** All of it, including the boring lines above and below. The part
that looks like noise is usually the part that identifies the problem.

**7. Skim what you get, and ask.** After each block, pick one file and ask me *"walk me
through this file in plain English."* Two minutes each. That is the difference between
finishing the weekend with a skill and finishing it with a folder.

---

## Friday night: 20 minutes of setup

Do this before Saturday so you start with momentum instead of installers.

### F.1 — Check Node.js

Node is what runs the frontend build tools. Open a terminal in the project folder:

```bash
node --version
```

**You should see:** `v20.x.x` or higher. (You are on `v24.15.0` — good.)

If you get "command not found", download the LTS installer from
[nodejs.org](https://nodejs.org), run it, **close the terminal, open a new one**, and try
again. The new terminal matters — an open one will not pick up the change.

### F.2 — Start the database

```bash
docker compose -f docker/docker-compose.yml up -d
```

**You should see:** a line ending in `Started` or `Running`.

**If it says** `failed to connect to the docker API` — Docker Desktop is not running. Open it
from the Start menu, wait for the whale icon to stop animating, try again.

**If it says** `bind: An attempt was made to access a socket in a way forbidden by its access
permissions` — this is the known Windows port problem documented in `CLAUDE.md`. Open
PowerShell **as Administrator**:

```
net stop winnat
net start winnat
```

Then retry the docker command.

### F.3 — Start the API

In the same terminal:

```bash
uv run fastapi dev main.py
```

**You should see:** `Uvicorn running on http://127.0.0.1:8000`.

The first start takes about ten seconds because of docling. That is normal and documented —
not a hang.

**Leave this terminal open all weekend.** You will open a second one for the frontend.

### F.4 — Confirm there is data

Open a **new** terminal (leave the API running):

```bash
curl http://127.0.0.1:8000/health
```

**You should see:** `{"status":"ok","chunks":879}` — your number may differ.

**If `chunks` is 0**, the database is empty and you need `uv run python ingest.py` first.
That costs money in OpenAI API calls, so do it Friday, not Saturday morning.

### F.5 — Confirm answers work

```bash
uv run python execute_api.py
```

**You should see:** a real answer with numbered sources printed underneath.

Five checks passed? You are ready. Go to bed.

---

# SATURDAY

---

## Block 1 (30 min) — Prepare the backend

Your API needs three changes before a browser can use it. I make them; you run the checks.

| Change | Why you need it |
|---|---|
| **CORS** | A browser refuses to let a page on one port read data from another port unless the server explicitly allows it. Without this nothing works, and the error message is confusing |
| **`chunks` in the response** | `/answer` currently throws the retrieved passages away before sending. The sources drawer needs them |
| **A streaming endpoint** | So text appears word by word instead of after an 8-second freeze. This is most of what makes it *feel* like Claude |

### Prompt 1.1

> ```
> Make the three backend changes for the chat UI:
>
> 1. Add CORSMiddleware to main.py allowing http://localhost:5173,
>    http://127.0.0.1:5173 and http://localhost:8000
>
> 2. Add a Chunk model and a `chunks` field to the Answer response model, so the
>    retrieved passages actually reach the browser
>
> 3. Add POST /answer/stream as a Server-Sent Events endpoint that emits a
>    `sources` event first, then `token` events, then `done`. Keep it `def`, not
>    `async def` — the OpenAI client blocks and would freeze the event loop.
>    Add generate_answer_stream to source/generate.py and make _source public.
>
> Do not add any new Python dependencies.
> ```

### Checkpoint 1

Your API terminal reloads by itself. Then run:

```bash
curl -N -X POST http://127.0.0.1:8000/answer/stream \
  -H "Content-Type: application/json" \
  -d '{"query":"what is gradient descent"}'
```

**You should see** text scrolling past in small pieces:

```
event: sources
data: [{"citation":1,"source":"Lecture-08_26.pdf",...}]

event: token
data: {"t":"Gradient"}

event: token
data: {"t":" descent"}
```

The `-N` flag tells curl not to buffer. Without it everything arrives at once and you will
think streaming is broken.

**If you get an error**, paste the whole thing plus your API terminal output to me.

```bash
git add -A && git commit -m "chat ui: CORS, chunks in response, streaming endpoint"
```

---

## Block 2 (45 min) — Create the frontend project

### 2.1 — Move the old page aside

Your `web/` folder already contains the plain `index.html` from the earlier guide. The
scaffolding tool refuses to write into a folder that is not empty, so move it:

```bash
mv web/index.html docs/legacy-plain-ui.html
```

Nothing is lost — it becomes a reference instead of the app.

### 2.2 — Scaffold the project

```bash
npm create vite@latest web -- --template react-ts
cd web
npm install
```

**In plain English:** *Vite* runs your frontend while you develop and rebuilds it instantly
when you save. *react-ts* means "React, with TypeScript." *npm install* downloads the
libraries into `web/node_modules` — a large folder you never open and never commit.

**You should see** a lot of output ending in something like `added 180 packages`.

### 2.3 — Add Tailwind and shadcn/ui

*Tailwind* is a styling system where you write classes like `flex gap-2 rounded-lg` directly
on elements instead of maintaining a separate CSS file. *shadcn/ui* is a set of ready-made
components that **copies its source code into your project** — you own it and can edit it.

```bash
npm install tailwindcss @tailwindcss/vite
npm install -D @types/node
```

Then three small config edits. **Ask me to make them rather than typing by hand** — the exact
shape of these files changes between tool versions:

### Prompt 2.1

> ```
> Configure Tailwind v4 and the "@" path alias in the new web/ project:
> - replace web/src/index.css with the tailwind import
> - add the tailwindcss plugin and the @ -> ./src alias to web/vite.config.ts
> - add baseUrl and the @/* path to web/tsconfig.json and web/tsconfig.app.json
> Then tell me the exact shadcn init command to run.
> ```

Then run what I give you, which will be close to:

```bash
npx shadcn@latest init
```

It asks a few questions. Sensible answers: base colour **Neutral**, CSS variables **yes**.

Then add the components you will need:

```bash
npx shadcn@latest add button textarea scroll-area avatar sheet badge skeleton separator tooltip
```

**You should see** new files appearing in `web/src/components/ui/`. Open
`web/src/components/ui/button.tsx` and look at it for ten seconds. That is what "you own the
code" means — a normal file in your project, not something hidden inside `node_modules`.

> **These tools move fast.** My knowledge has a cutoff, and shadcn and Tailwind both change
> their setup steps periodically. If any command prints something unexpected, paste the
> output to me and I will adapt. You are never stuck — that is the whole advantage of doing
> this with me in the loop rather than from a static tutorial.

### 2.4 — Ignore the right things

```bash
cd ..
printf 'web/node_modules/\nweb/dist/\n' >> .gitignore
```

`node_modules` is hundreds of megabytes of downloaded code. It must never go into git.

### Checkpoint 2

```bash
npm --prefix web run dev
```

**You should see** `Local: http://localhost:5173/`. Open that in your browser.

You get the default Vite starter page with a spinning React logo and a counter button. It is
ugly. That is correct — it proves the toolchain works.

**Leave this running.** You now have two terminals: API on 8000, frontend on 5173. Every time
you save a file the browser updates in under a second without losing your place.

```bash
git add -A && git commit -m "chat ui: vite + react + tailwind + shadcn scaffold"
```

---

## Block 3 (90 min) — Build the look, with fake data

**The most important trick in this guide:** build the appearance first, using hardcoded fake
messages. No API calls yet.

Why this works so well: you iterate on how it looks in a one-second loop instead of waiting
eight seconds for a real answer every time — and you never confuse "the layout is wrong" with
"the request failed."

### Prompt 3.1

> ```
> Build the static chat shell in web/src/App.tsx using shadcn components and
> Tailwind. Use 4 hardcoded fake messages — no API calls, no fetch, nothing async.
>
> Layout requirements:
> - Fills the viewport height exactly. The page body must NEVER scroll — only the
>   message list scrolls, with the header and composer staying put.
> - Header: app title on the left, a placeholder "879 chunks" badge on the right,
>   thin bottom border.
> - Message list: centered column, max-width 48rem, generous vertical spacing.
> - User messages: rounded bubble, muted background, aligned right, max 80% width.
> - Assistant messages: NO bubble, full width, plain text, small icon on the left.
> - Composer pinned at the bottom: a rounded container holding a textarea that
>   grows as you type (capped around 200px, then it scrolls) and a circular send
>   button on the right with an up-arrow icon.
> - Send button disabled when the textarea is empty.
>
> Keep it in one file for now — I want to see the shape before we split it up.
> ```

### Checkpoint 3

Look at `http://localhost:5173`.

**You should see** a header, four messages in the right shapes, and a text box at the bottom
that grows taller as you type more lines. Nothing sends yet — that is the next block.

### Now iterate — this is the actual vibe coding

Look at it and tell me what is off. Real examples of good feedback:

- "The user bubble is too wide, it should hug the text"
- "There is no space between messages, they run together"
- "The composer is touching the bottom edge of the window"
- "The header text is bigger than the message text, it should be smaller"
- "It looks cramped — everything needs more breathing room"

One at a time. Commit when you like it.

### The layout detail that always breaks

If the whole page scrolls instead of just the message list, the fix is almost always this
structure:

```tsx
<div className="flex h-screen flex-col">
  <header className="shrink-0 border-b">...</header>

  <div className="flex-1 min-h-0 overflow-y-auto">   {/* ← min-h-0 is the tricky bit */}
    <div className="mx-auto max-w-3xl px-4 py-6">...</div>
  </div>

  <div className="shrink-0 border-t">...</div>
</div>
```

`h-screen` locks it to the window height. `flex-1` makes the middle section take whatever
space is left over. `min-h-0` is the non-obvious one — without it, a flex child refuses to
shrink below its content size, and the scrollbar ends up on the whole page instead of on the
list. If scrolling misbehaves, just say *"the page scrolls instead of just the message list"*
and I will check this first.

```bash
git add -A && git commit -m "chat ui: static shell with fake messages"
```

---

## Block 4 (60 min) — Wire in the real API

Replace the fake messages with real ones. Still no streaming — one request, wait, show the
whole answer. Get this working before adding streaming on top of it.

### Prompt 4.1

> ```
> Wire the chat UI to the real API, non-streaming for now.
>
> Create web/src/api.ts holding ONLY transport — no React in this file:
> - TypeScript interfaces mirroring the Pydantic models in main.py
>   (Source, Chunk, AnswerResponse, HealthResponse)
> - ask(), search() and health() functions using fetch
> - check res.ok explicitly, since fetch does NOT throw on 4xx/5xx
> - normalise FastAPI errors: `detail` is a string for HTTPException but an ARRAY
>   of objects for 422 validation errors. Turn both into one readable string.
> - accept an AbortSignal on each request
>
> Then in App.tsx:
> - messages state: ChatMessage[] with id, role, content, sources, chunks, status
> - on send: append the user message, call ask(), append the assistant message
> - disable the composer while a request is in flight
> - show a "thinking" indicator where the assistant message will appear
> - show a readable error message in the thread if the request fails
> - replace the hardcoded 879 with a real /health call when the app loads
> ```

### Checkpoint 4

Type a real question about your PDFs and press Enter.

**You should see** your message appear immediately, a thinking indicator for a few seconds,
then the real answer replacing it.

**If nothing happens and the browser console mentions CORS:** the Block 1 change did not
apply. Check that your API terminal actually reloaded. Press `F12` in the browser, click
**Console**, and paste anything red to me.

**If you see "Failed to fetch" with no CORS mention:** the API is not running. Check terminal 1.

```bash
git add -A && git commit -m "chat ui: real API calls, non-streaming"
```

---

## Block 5 (90 min) — Streaming

The block that makes it feel like a real product. Same total time, completely different
experience — words start appearing about a second in, instead of nothing for eight seconds.

### Prompt 5.1

> ```
> Add streaming to the chat UI using the /answer/stream endpoint.
>
> In api.ts add askStream(query, handlers, signal) that:
> - POSTs with fetch (NOT EventSource — that only does GET, and our endpoint is POST)
> - reads res.body through TextDecoderStream
> - buffers partial events: network chunks do NOT align with event boundaries, so
>   split on the blank line and keep the incomplete tail for the next read
> - calls onSources / onToken / onError / onDone
>
> In App.tsx:
> - append an empty assistant message with status "streaming" before the request
> - append each token to that last message using the FUNCTIONAL setState form
>   (setMessages(prev => ...)) — the other form loses most tokens
> - render a blinking cursor at the end while status is "streaming"
> - set status to "done" on the done event
> ```

### Checkpoint 5

Ask a question.

**You should see** sources appear almost immediately, then text arriving word by word with a
blinking cursor at the end.

**If the text arrives all at once at the end**, tell me — usually a missing blank line
between events on the server side.

**If most of the words are missing** — you see something like "Backpropagation the rule the
network" — that is the stale closure problem. Say *"tokens are being dropped"* and I will fix
the setState call.

### The one line worth actually understanding

```tsx
setMessages(prev => { ... })     // ✅ always receives the newest state
setMessages([...messages, x])    // ❌ uses the state from when this function was created
```

With a token arriving every few milliseconds, the second form silently loses most of them.
This is one of maybe three genuinely subtle things in React, and streaming is where you meet
it. Worth two minutes of asking me to explain it properly.

```bash
git add -A && git commit -m "chat ui: streaming answers"
```

---

## Saturday checkpoint

You now have a working chat interface: type a question, watch a grounded answer stream in,
with sources listed underneath. It looks a bit plain, and Markdown shows as raw `##` and `-`
characters. Sunday fixes both.

**If you are behind, stop here anyway.** A working plain version is worth more than a
half-finished pretty one. Sunday's blocks are all independent — do them in any order, skip
any of them.

---

# SUNDAY

---

## Block 6 (60 min) — Markdown and code blocks

Right now the model's `##` headings and `-` bullets show as literal characters. Fixing this
is the single biggest visual upgrade left.

```bash
npm --prefix web install react-markdown remark-gfm
npm --prefix web install -D @tailwindcss/typography
```

### Prompt 6.1

> ```
> Render assistant messages as Markdown:
> - use react-markdown with remark-gfm
> - add the @tailwindcss/typography plugin and use prose classes, sized to match
>   the rest of the UI and working in dark mode
> - style code blocks: subtle background, rounded, horizontal scroll for long
>   lines, monospace
> - add a small copy button in the top-right corner of every code block that
>   shows a checkmark for two seconds after clicking
> - user messages stay plain text, NOT markdown
>
> Do NOT add rehype-raw or use dangerouslySetInnerHTML anywhere.
> ```

### Why that last line matters

Model output is text you did not write, partly derived from documents. React escapes strings
by default, which means `<script>` renders as visible characters rather than running.
`dangerouslySetInnerHTML` throws that protection away. The name is a warning, not a joke.
`react-markdown` is safe by default because it builds React elements rather than parsing HTML
— unless you add `rehype-raw`, which re-enables raw HTML. Do not.

### Checkpoint 6

Ask something that produces a list or a code block.

**You should see** proper bullets, proper headings, and code in a distinct block with a copy
button.

```bash
git add -A && git commit -m "chat ui: markdown rendering and code blocks"
```

---

## Block 7 (60 min) — Citations and the sources drawer

**This is the block that makes your app different from a generic chatbot**, and the reason
building RAG was worth the effort. Anyone can show an answer. Showing the exact passage it
came from is what makes the system inspectable.

Your prompt in `source/generate.py` tells the model to cite with `[1]`, `[2]`, and `_source()`
numbers the sources with the same `enumerate(chunks, start=1)`. So citation `n` always
corresponds to the chunk at `rank === n`. That convention is what makes this block easy.

### Prompt 7.1

> ```
> Add citations and a sources drawer.
>
> In the assistant message:
> - find [1], [2] etc. in the answer text and render each as a small clickable
>   chip (superscript, rounded, subtle background)
> - under the answer, a collapsible "Sources" section listing each source with
>   filename, page numbers and headings
>
> Clicking either a chip or a source row opens a shadcn Sheet from the right
> showing:
> - which passage number it is
> - the filename (strip the Windows directory path — metadata.source holds a full
>   path like C:\Users\...\data\Lecture-08_26.pdf, so split on both / and \)
> - page numbers and the RRF score
> - the FULL chunk text in a readable, scrollable block
>
> Escape closes the drawer. Do not modify metadata.source itself — document
> identity depends on that string staying byte-identical.
> ```

### Checkpoint 7

Ask a question, then click a `[1]` chip.

**You should see** a panel slide in from the right containing the actual paragraph from your
PDF that the model used.

Read one. This is the moment the whole system becomes real — you can now tell "retrieval
found the wrong passage" apart from "retrieval was fine but the model fumbled it." That
distinction is exactly what your Phase 3 evaluation work exists to measure, and now you can
see it by clicking.

```bash
git add -A && git commit -m "chat ui: citation chips and sources drawer"
```

---

## Block 8 (60 min) — The details that make it feel real

Individually tiny. Together they are the entire difference between "a demo" and "an app."

### Prompt 8.1

> ```
> Add the chat interaction details, one commit each:
>
> 1. Smart auto-scroll: follow the bottom as tokens stream in, but STOP following
>    the moment the user scrolls up, and resume when they scroll back to the
>    bottom. Show a "jump to latest" button while they are scrolled away.
>    Use instant scrolling during streaming, not smooth — smooth on every token
>    is janky.
>
> 2. Enter sends, Shift+Enter makes a new line. Guard against IME composition so
>    it does not fire mid-word for languages that use a candidate picker.
>
> 3. Return focus to the textarea after sending, and clear it.
>
> 4. A "Stop" button that appears while streaming and aborts the request with
>    AbortController. Keep the partial text that already arrived.
>
> 5. A copy button on each finished assistant message.
> ```

### Why auto-scroll is item one

It is the detail everyone gets wrong. The naive version scrolls to the bottom on every token,
which means if you scroll up to re-read something while the answer is still streaming, it
yanks you back down every 40 milliseconds. Unusable.

The fix is one piece of state: are we currently "stuck" to the bottom? Set it to false when
the user scrolls more than ~80px away, back to true when they return, and only auto-scroll
while it is true.

```tsx
const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
setStick(distanceFromBottom < 80);
```

### Checkpoint 8

Ask a long question. While it is streaming, scroll up.

**You should see** the page stay where you put it, with a "jump to latest" button appearing.
Click it and you snap back to following along.

```bash
git add -A && git commit -m "chat ui: scroll, keyboard, stop button, copy"
```

---

## Block 9 (45 min) — Empty state, suggestions, dark mode

### Prompt 9.1

> ```
> Add the finishing touches:
>
> 1. Empty state: when there are no messages, center a short greeting in the
>    message area with 3 clickable suggestion chips. Clicking one puts that text
>    in the composer and focuses it. Use questions that suit an ML lecture corpus.
>
> 2. Dark mode: a sun/moon toggle in the header. Default to the system setting,
>    remember the user's choice in localStorage, apply it by toggling the "dark"
>    class on <html> so the shadcn CSS variables switch.
>
> 3. Respect prefers-reduced-motion: no blinking cursor, no shimmer for users who
>    have that turned on.
>
> 4. Accessibility basics: aria-live="polite" on the streaming message so screen
>    readers announce it, role="alert" on errors, visible focus rings everywhere.
> ```

### Checkpoint 9

Reload with an empty thread.

**You should see** a clean centered greeting with three suggestions. Click the moon icon —
everything should switch to dark without a flash of white. Reload — it should remember.

```bash
git add -A && git commit -m "chat ui: empty state, dark mode, accessibility"
```

---

## Block 10 (30 min) — Ship it: one URL, no CORS

Right now you need two terminals. Let's make FastAPI serve the frontend too, so the whole app
lives at `http://127.0.0.1:8000`.

### 10.1 — Build the frontend

```bash
npm --prefix web run build
```

**In plain English:** this compresses your whole frontend into plain HTML, CSS and JavaScript
files in `web/dist/`. No Node needed to *run* it — only to build it.

**You should see** output ending with a list of generated files and their sizes.

### Prompt 10.1

> ```
> Serve the built frontend from FastAPI:
> - mount StaticFiles on "/" pointing at web/dist, with html=True
> - it MUST be declared after every API route, or it will swallow /health,
>   /search and /answer
> - guard it with a directory-exists check so `fastapi dev` still starts before
>   anyone has run a build
> - set VITE_API_URL="" for the production build so the frontend calls its own
>   origin instead of a hardcoded 127.0.0.1:8000
> ```

### Checkpoint 10

Stop the frontend terminal (`Ctrl+C`). Open `http://127.0.0.1:8000` in your browser.

**You should see** your full chat app, served by Python, on one port, with no CORS involved.

**Remember:** `dist/` is a snapshot. Change a frontend file and you must re-run
`npm --prefix web run build` to see it here. For day-to-day work keep using the Vite dev
server on 5173 — build only when you want to check the real thing.

```bash
git add -A && git commit -m "chat ui: serve built frontend from FastAPI"
```

**You are done.** Everything below is optional.

---

## Block 11 (optional) — Real conversation memory

Right now every question is independent. Ask "how does backprop work?" then "can you explain
that more simply?" and the second one retrieves and answers as if the first never happened —
because your `/answer` endpoint receives only a single `query` string.

Users will try this within about ninety seconds of using your app, so it is worth knowing
what it costs.

### Prompt 11.1

> ```
> Add multi-turn conversation memory:
>
> Backend:
> - add a Turn model (role, content) and a `history: list[Turn] = []` field to Query
> - in generate_answer and generate_answer_stream, insert the history between the
>   system prompt and the current question
> - keep retrieval using ONLY the latest question for now
> - cap history at the last 6 turns so the prompt does not grow forever
>
> Frontend:
> - send the previous messages along with each new question
> ```

### The honest limitation

Retrieval still runs on the raw latest question. So "what about the second one?" embeds the
literal words *"what about the second one?"* — which matches nothing useful in your corpus.
The model will have the conversation in its prompt but the *wrong passages* alongside it.

The real fix is **query rewriting**: a cheap model call that turns "what about the second
one?" plus the history into a standalone question like "what is the second optimizer
mentioned in Lecture 8?", and you retrieve on *that*. It is maybe thirty lines and one extra
API call per turn.

That is a genuinely interesting piece of RAG engineering and it does not belong in a weekend.
Note it as the next project.

---

## Appendix A: every prompt in one place

Copy-paste, in order.

| Block | Prompt |
|---|---|
| 1 | Make the three backend changes: CORS, chunks in the Answer model, /answer/stream as SSE. Keep endpoints `def`. No new Python dependencies. |
| 2 | Configure Tailwind v4 and the @ alias in web/, then tell me the shadcn init command. |
| 3 | Build the static chat shell with 4 fake messages. Viewport height, only the list scrolls, user bubbles right, assistant full width, auto-growing composer pinned at the bottom. |
| 4 | Create api.ts (transport only, no React) and wire real non-streaming calls with proper error handling. |
| 5 | Add askStream with SSE parsing and buffering; append tokens with the functional setState form. |
| 6 | Render Markdown with react-markdown + typography, styled code blocks with copy buttons. No rehype-raw. |
| 7 | Citation chips, collapsible sources list, and a Sheet drawer showing the full chunk text. |
| 8 | Smart auto-scroll, Enter/Shift+Enter, refocus, Stop button, copy button. |
| 9 | Empty state with suggestions, dark mode toggle, reduced motion, accessibility basics. |
| 10 | Mount StaticFiles after the routes to serve web/dist from FastAPI. |
| 11 | Optional: conversation history in the prompt, capped at 6 turns. |

---

## Appendix B: when something breaks

| What you see | What it means | What to say to me |
|---|---|---|
| Blank white page | A JavaScript error stopped rendering | Press F12 → Console, paste everything red |
| "Failed to fetch" + CORS in the console | The browser blocked the request | "CORS is blocking the frontend" |
| "Failed to fetch", no CORS message | API not running, or wrong port | Check terminal 1 is still running |
| Answer appears all at once | Streaming is not actually streaming | "The answer arrives all at once instead of word by word" |
| Half the words missing | Stale closure in the token handler | "Tokens are being dropped" |
| The whole page scrolls | Missing `min-h-0` on the flex child | "The page scrolls instead of just the message list" |
| Text yanks back down while reading | Auto-scroll ignoring the user | "It scrolls me back down when I scroll up" |
| Raw `##` and `-` in answers | Markdown not being rendered | Block 6 not done |
| `[object Object]` in an error message | Rendering a 422 detail array as a string | "The error shows as object Object" |
| Composer is frozen, cannot type | A controlled input missing its onChange | "I cannot type in the text box" |
| Page flashes and clears on send | Missing `e.preventDefault()` | "The page reloads when I press send" |
| `npm` command not found | Node not installed, or terminal not restarted | Re-do step F.1 in a **new** terminal |
| Build works, page blank at :8000 | Wrong asset base path, or mount order | "The built page is blank but dev works" |
| `/health` returns HTML | StaticFiles mounted before the API routes | "The API routes return the webpage" |

**Universal fallback:** `git reset --hard HEAD` returns you to your last commit. This is why
rule 1 exists.

---

## Appendix C: what to actually learn from this

You will finish with a working app either way. To finish with a *skill*, read exactly three
files and ask me to walk you through each:

1. **`web/src/api.ts`** — every request your app makes. If you understand this file, you
   understand how any frontend talks to any backend. It is the most reusable thing here.

2. **The message state in `App.tsx`** — how a list of messages gets appended to and updated
   immutably. This is the shape of every chat app that exists.

3. **The streaming handler** — how bytes off the network become words on screen. This is the
   piece most people never look at, and it is genuinely interesting.

Skip the components. `MessageBubble.tsx` teaches you nothing you cannot re-derive; those
three teach you the transferable parts.

**Then, when you build your next AI app**, the reusable spine is: `api.ts`, the message state,
and the streaming handler. The components change per project. That skeleton does not.

**Good next steps, roughly in order:**

- [react.dev/learn](https://react.dev/learn) — "Describing the UI" and "Adding Interactivity"
  only. Four to six hours, and everything in this weekend will suddenly make sense in
  hindsight.
- Query rewriting for real multi-turn RAG (the interesting problem from Block 11).
- Persisting conversations — a `conversations` table, and your first real database work on
  the app side rather than the retrieval side.
- [Flexbox Froggy](https://flexboxfroggy.com) — thirty minutes, genuinely fixes most layout
  confusion.

---

## Appendix D: what this weekend changes in your repo

| File | Change | Block |
|---|---|---|
| `main.py` | CORS middleware | 1 |
| `main.py` | `Chunk` model + `chunks` on `Answer` | 1 |
| `main.py` | `POST /answer/stream` | 1 |
| `main.py` | `StaticFiles` mount, after the routes | 10 |
| `source/generate.py` | `generate_answer_stream`, `_source` → `sources` | 1 |
| `source/generate.py` | history in the prompt | 11 (optional) |
| `web/index.html` | moved to `docs/legacy-plain-ui.html` | 2 |
| `web/` | the whole React app | 2–10 |
| `.gitignore` | `web/node_modules/`, `web/dist/` | 2 |

**No new Python dependencies.** `CORSMiddleware`, `StreamingResponse` and `StaticFiles` all
ship with `fastapi[standard]`, which keeps invariant 7 in `CLAUDE.md` intact. The Node
packages live entirely under `web/` and are needed only at build time.

One thing worth knowing before you spend a weekend making retrieval visible: `CLAUDE.md`
records **195 orphaned chunks** — rows in Postgres whose PDFs were deleted from `data/`. In a
terminal that is a stale file path in a citation. In this UI it is a drawer that proudly
displays the full text of a document that no longer exists. Worth cleaning up first; it is a
single SQL query and a few `remove_by_source` calls.
