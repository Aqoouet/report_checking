# Configuration

The root `.env.example` is the canonical source of truth for Docker and
deployment defaults.

Service-local examples are intentionally smaller overlays:

- `backend/.env.example` is for running the backend directly with Python or
  uvicorn on the host.
- `frontend/.env.example` is for running Vite directly on the host.

Do not introduce a new default in a service-local example without also checking
the root `.env.example` and the README table.

## Default Ownership

| Variable group | Owner | Canonical file |
| --- | --- | --- |
| LLM endpoint, model, timeout, chunk limits | Backend runtime | `.env.example` |
| Docker ports, mounted storage, container user | Compose/deployment | `.env.example` |
| Direct backend development URL/model placeholders | Backend local overlay | `backend/.env.example` |
| Direct frontend API URL | Frontend local overlay | `frontend/.env.example` |

## Error And Log Contract

Backend API failures should return:

```json
{
  "detail": {
    "code": "ERR_EXAMPLE",
    "message": "English developer-facing message."
  }
}
```

Backend logs and backend error catalog messages are English. The frontend owns
localized user-facing copy by mapping error codes to UI messages.
