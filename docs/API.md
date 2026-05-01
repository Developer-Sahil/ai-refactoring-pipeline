# API Documentation — AI Refactoring Pipeline v1

## Base URL
- **Local (Dev)**: `http://localhost:8000`
- **Docs (Swagger)**: `http://localhost:8000/docs`

## Authentication
Currently open (dev mode). **Firebase Auth** JWT token validation via Firebase Admin SDK planned for production. Pass `Authorization: Bearer <firebase_id_token>` on protected routes.

---

## Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health probe |

---

### Pipeline Jobs

#### Submit a Refactoring Job
`POST /api/v1/refactor`

Upload a `.py` file and enqueue a background refactoring job.

**Form fields:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `files` | File[] | required | One or more `.py` files, or a single `.zip` archive |
| `model` | string | `gemini-2.5-flash` | LLM model name |
| `batch_size` | int | 3 | Functions per prompt batch |
| `delay` | float | 2.0 | Throttle delay (seconds) |
| `in_place` | bool | false | Overwrite original files |
| `no_functional` | bool | false | Skip behavioral/functional validation in Stage 4 |

**Upload modes supported:**
- Single `.py` file
- Multiple `.py` files (multi-select)
- Folder via browser (`webkitdirectory` — browser sends each file individually)
- `.zip` archive (extracted server-side; all `.py` inside are processed)

**Response** `202 Accepted`:
```json
{
  "job_id": "uuid",
  "status": "queued",
  "ws_url": "ws://localhost:8000/api/v1/ws/{job_id}"
}
```

---

#### Get Job Status
`GET /api/v1/status/{job_id}`

**Response** `200 OK`:
```json
{
  "job_id": "uuid",
  "filename": "source.py",
  "status": "running",
  "stage": 2,
  "stage_label": "prompt_builder",
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "error": null
}
```

Possible `status` values: `queued` | `running` | `completed` | `failed`
Possible `stage` values: 0 (idle) → 1 (cAST) → 2 (prompt_builder) → 3 (llm_agent) → 4 (validator) → 5 (done)

---

#### Get Job Results
`GET /api/v1/results/{job_id}`

Only available once `status` is `completed` or `failed`.

**Response** `200 OK`:
```json
{
  "job_id": "uuid",
  "filename": "source.py",
  "status": "completed",
  "exit_code": 0,
  "refactored_code": "...",
  "validation_report": { "severity": "pass", "pass_rate": 1.0, "checks": {} },
  "stdout": "...",
  "stderr": ""
}
```

---

#### List All Jobs
`GET /api/v1/jobs`

Returns a summary array of all jobs in the current session, newest first.

---

### WebSocket — Real-Time Stage Updates
`WS /api/v1/ws/{job_id}`

Connect to receive live stage-change events as the pipeline progresses.
Each message is the full job state object (same shape as `/status`).
The connection closes gracefully once the job reaches `completed` or `failed`.

---

## Error Codes
| Code | Meaning |
|------|---------|
| 400 | Invalid file type (only `.py` accepted) |
| 404 | Job not found |
| 425 | Job still running — results not ready |
| 500 | Internal server error |

