# API Reference — Multi-Agent Publication Generator

This document provides a concise reference for integrating with the multi-agent publication generator. For SDK-style usage see the `agents` package and `agents/langgraph_coordinator.py`.

## REST API (recommended)

Base path: `/api/v1`

### POST /publications
Create a new publication job.

Request JSON:
```json
{
  "repo_url": "https://github.com/user/repo",
  "output_format": "pdf|md",
  "quality_level": "quick|comprehensive",
  "notify_url": "https://example.com/webhook"  
}
```

Responses:
- 202 Accepted
```json
{ "job_id": "uuid-v4", "status": "queued" }
```
- 400 Bad Request — invalid payload
- 401 Unauthorized — missing/invalid API key

### GET /publications/{job_id}
Retrieve job status and metadata.

Response 200:
```json
{
  "job_id": "uuid-v4",
  "status": "queued|processing|completed|failed",
  "progress": 0-100,
  "started_at": "2025-11-21T12:00:00Z",
  "finished_at": null,
  "result": { "download_url": "https://.../artifact.pdf" },
  "errors": []
}
```

### GET /publications/{job_id}/download
Redirect or return the generated artifact (PDF/Markdown).
- 302 Found (redirect to external storage) or 200 OK with binary payload.

### DELETE /publications/{job_id}
Cancel or remove a job (if still queued/processing).
- 204 No Content on success.

## Authentication
- Use an API key in the `Authorization` header: `Authorization: Bearer <API_KEY>`
- Optionally support OAuth2 for enterprise integrations.

## Rate Limiting & Headers
- Responses should include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.
- On rate limit exceeded return 429 Too Many Requests with `Retry-After` header.

## Error Model
Standard error response:
```json
{
  "code": "string",
  "message": "Human readable message",
  "details": { }
}
```
Common codes: `invalid_input`, `unauthorized`, `rate_limited`, `internal_error`, `provider_unavailable`.

## Webhooks (optional)
- `POST` to `notify_url` when job completes/ fails.
- Payload includes `job_id`, `status`, `download_url`, and `correlation_id`.

## Programmatic (Python) usage
Example using the coordinator API:

```python
from agents.langgraph_coordinator import MultiAgentCoordinator
from config.environment import get_config

config = get_config()
coordinator = MultiAgentCoordinator(config)
result = coordinator.process_repository(
    repo_url="https://github.com/example/repo",
    output_format="pdf",
    quality_level="comprehensive"
)
print(result.get_publication_path())
```

## CLI (example)
```
# Generate a publication using the CLI wrapper
python -m multiagent.cli generate --repo https://github.com/user/repo --format pdf
```

## Best Practices
- Use `quality_level=quick` for small repositories or preview runs to save tokens and time.
- Provide a `notify_url` for asynchronous processing and avoid polling.
- Protect endpoints behind an API gateway with rate limiting and authentication.

## Implementation Notes for Integrators
- Jobs are idempotent for the same `repo_url` + `output_format` when re-run within a short window; consider deduping on the server.
- Large repositories may be chunked; expect `processing` durations to vary with repo size and LLM provider latency.

## Contact & Support
For API issues open an issue at: https://github.com/SosiSis/Gen-Authering/issues and include `job_id` and `correlation_id` where available.
