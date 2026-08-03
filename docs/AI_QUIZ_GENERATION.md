# AI Quiz Generation

Flagship host feature: generate quizzes from uploaded study material or a topic, review section-wise drafts, then save into the existing QuizArena quiz builder as a **Draft**.

## Host flow

1. **My Quizzes** → **Generate with AI** (`/admin/quizzes/ai`)
2. Choose mode: **Topic** or **Upload material**
3. Configure question count, difficulty, question types, optional title
4. Start generation → progress page (`/admin/quizzes/ai/:jobId`)
5. Review sections / edit / delete / regenerate → **Save quiz**
6. Continues in the normal quiz builder (`/admin/quizzes/:quizId?step=2`)

## Modes

| Mode | Input | Pipeline |
|------|--------|----------|
| Document | PDF, PPT/PPTX, DOC/DOCX, PNG/JPG, MP4, TXT | Extract → normalize → chunk → embed → structure → questions |
| Topic | Free-text topic | Outline from AI + trusted source attribution → questions |

YouTube URL ingestion is reserved for a later iteration.

## Architecture

```
API (/api/v1/ai/*)
  → AiGenerationService (orchestration)
      → extractors (optional heavy deps)
      → chunking + embeddings (JSON on chunks; pgvector-ready)
      → AiProvider (mock | openai_compatible)
      → prompt files (services/ai/prompt_files/*.txt)
  → ai_job_worker (asyncio background queue)
  → AiSaveService → existing Quiz / Section / Question / Option services
```

### Tables (dedicated AI schema; embeddings never on quiz tables)

- `ai_generation_jobs` — async job + settings + status
- `ai_source_files` — uploaded binaries metadata
- `ai_document_chunks` — text chunks + `embedding_json`
- `ai_generated_sections` / `ai_generated_questions` — review draft
- `ai_source_references` — document name / trusted URLs

Migration: `alembic/versions/20260803_1300_ai_generation.py`

### AI provider abstraction

Supported `AI_PROVIDER` values:

| Provider | Transport | API key | Typical use |
|----------|-----------|---------|-------------|
| `openai` | OpenAI Chat Completions | Required | Production default |
| `openrouter` | OpenAI-compatible | Required | Multi-model gateway |
| `gemini` | Google AI Studio OpenAI-compatible API | Required | Free Gemini API (`generativelanguage.googleapis.com`, not Vertex) |
| `anthropic` | Anthropic Messages API | Required | Claude |
| `ollama` | OpenAI-compatible (local) | Optional | Local development |
| `openai_compatible` | OpenAI-compatible | Required | Azure / custom gateways |
| `mock` | In-process | — | **`APP_ENV=test` only** |

Startup validation (non-test): missing/invalid `AI_PROVIDER` or missing `AI_API_KEY` (except Ollama) **refuses to start** with a clear log — the API never reaches runtime `AI_CONFIG_ERROR` for misconfiguration.

Topic and document pipelines both call the same resolved `AiProvider` (`chat_json` + `embed`).

Placeholder / template questions (`concept #1`, `Distractor A`, etc.) are rejected by a quality gate; failed generations mark the job **FAILED** instead of saving fakes.

Prompts live in files under `backend/app/services/ai/prompt_files/` and are loaded via `prompts.py` — not hardcoded in services.

### Background jobs

`ai_job_worker` starts in FastAPI lifespan (same pattern as auto-progression). Status flow:

`queued` → `uploading` / `extracting` → `analyzing` → `generating` → `completed` | `failed` | `cancelled`

On a **single Render dyno**, jobs run in-process. Multi-instance deployments should move the worker to a shared queue (Redis/RQ/Celery) without changing the API contract.

## REST API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/ai/generate/document` | Create document job (**202**) |
| POST | `/ai/generate/topic` | Create topic job + schedule (**202**) |
| POST | `/ai/upload` | Multipart upload + schedule (**202**) |
| GET | `/ai/jobs` | Recent jobs |
| GET | `/ai/jobs/{id}` | Status + draft |
| GET | `/ai/generated/{id}` | Alias of job detail |
| POST | `/ai/jobs/{id}/cancel` | Cancel |
| PATCH | `/ai/question/{id}` | Edit draft question |
| DELETE | `/ai/question/{id}` | Delete draft question |
| POST | `/ai/regenerate/question/{id}` | Regenerate one question |
| POST | `/ai/regenerate/section/{id}` | Regenerate a section |
| POST | `/ai/regenerate/quiz/{id}` | Full re-run (**202**) |
| POST | `/ai/save` | Persist as Draft quiz (idempotent) |

Jobs run via FastAPI **BackgroundTasks** (not `asyncio.create_task` from sync threadpool handlers). On completion the quiz is **auto-saved** into My Quizzes as a Draft.

## Environment

| Variable | Default | Notes |
|----------|---------|--------|
| `AI_PROVIDER` | `mock` | `openai` / `openrouter` / `gemini` / `anthropic` / `ollama` / `openai_compatible` (`mock` = tests only) |
| `AI_API_KEY` | empty | Required except `ollama` |
| `AI_API_BASE_URL` | preset | Optional override of provider base URL |
| `AI_CHAT_MODEL` | preset | Chat model id |
| `AI_EMBEDDING_MODEL` | preset | Embedding model (`local` for hash vectors) |
| `AI_MAX_SOURCE_BYTES` | `52428800` (50 MiB) | Per-file upload cap |
| `AI_ENABLE_TOPIC_WEB` | `true` | Trusted-source seeding for topic mode |

### Render (production)

Set secrets on the web service (also listed in `render.yaml`):

```env
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_CHAT_MODEL=gpt-4o-mini
AI_EMBEDDING_MODEL=text-embedding-3-small
```

OpenRouter example:

```env
AI_PROVIDER=openrouter
AI_API_KEY=sk-or-...
AI_CHAT_MODEL=openai/gpt-4o-mini
```

Ollama (local development):

```env
AI_PROVIDER=ollama
AI_CHAT_MODEL=llama3.2
# AI_API_KEY optional
```

### Google AI Studio (Gemini free API)

Uses `https://generativelanguage.googleapis.com/v1beta/openai` (AI Studio), **not** Vertex AI.

```env
AI_PROVIDER=gemini
AI_API_KEY=<key from https://aistudio.google.com/apikey>
AI_CHAT_MODEL=gemini-2.5-flash
AI_EMBEDDING_MODEL=gemini-embedding-001
```

Do **not** set `AI_API_BASE_URL` unless you intentionally override the preset (leave it unset on Render).

### Optional extractors (production)

Install as needed (see `backend/requirements.txt` comments):

- PDF: `pymupdf`
- PPT/PPTX: `python-pptx` (+ OCR for image slides)
- DOCX: `python-docx`
- Images: Tesseract / `pytesseract`
- Video: Whisper

Without optional deps, TXT always works; other types fail with a clear extraction error.

## Quality rules (enforced in prompts + review UX)

- Section-aware generation (not random whole-doc sampling)
- Explanations + topic + source locator per question
- Meaningful distractors; avoid verbatim copy
- Host can edit / regenerate before save

## Future extensions

Architecture keeps generation jobs and drafts separate from live quizzes so you can add flashcards, study notes, practice mode, adaptive difficulty, AI tutor, voice quiz, and PDF summaries without reshaping the quiz runtime.

## Tests

```bash
cd backend
pytest tests/unit/test_ai_generation.py tests/integration/test_ai_generation.py -q
```

Mock provider is used unless `AI_PROVIDER` is overridden.
