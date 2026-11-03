# Vectra — Infra

Brings up the whole stack: Postgres/TimescaleDB, Redis, MinIO, and all five
Vectra services, wired together exactly as described in `contracts/README.md`.

## Layout expected

This folder assumes the full repo layout:

```
vectra/
├── contracts/
├── backend/
├── signal-service/
├── camera-ingestion-service/
├── police-case-service/
├── frontend/
└── infra/            <- you are here
```

Every service's `Dockerfile` copies the sibling `contracts/` folder into its
image (for the shared `vectra_contracts` Python package), so all builds use
`context: ..` (the `vectra/` root) — don't move `infra/` out of the repo root.

## Run everything

```bash
cd infra
docker compose up --build
# or: make up
```

First boot takes a minute (Postgres init, `pip install`, `npm install` for
the frontend build). Once it settles:

| Service | URL | Notes |
|---|---|---|
| Frontend (dashboard) | http://localhost:8080 | proxies `/api` and `/ws` to backend internally; shows live signal state + annotated camera frames |
| Backend API | http://localhost:8000/api/v1 | e.g. `/health`, `/intersections`, `/intersections/{id}/stats` |
| Backend WebSocket | ws://localhost:8000/ws/intersections/{id} | push channel the dashboard uses instead of polling |
| signal service | http://localhost:8100/api/v1 | `/infer/signal-decision` for manual testing |
| Camera ingestion | http://localhost:8200/api/v1 | `/cameras`, `/cameras/{id}/frames` |
| Police case service | http://localhost:8300/api/v1 | `/cases` |
| MinIO console | http://localhost:9001 | login `vectra` / `vectra123` |
| Postgres | localhost:5432 | `vectra` / `vectra` / db `vectra` |
| Redis | localhost:6379 | pub/sub channels below |

## Seeing the full pipeline run

1. Register an intersection:
   ```bash
   curl -X POST http://localhost:8000/api/v1/intersections \
     -H "Content-Type: application/json" \
     -d '{"name":"Main Rd x Bypass","latitude":9.93,"longitude":77.48,"lane_groups":["north","south","east","west"]}'
   ```
2. Register a camera on that intersection and push a test frame through it:
   ```bash
   cd ../camera-ingestion-service
   pip install requests
   python scripts/send_test_frame.py --intersection <id-from-step-1> --lane north --image any.jpg
   ```
3. Watch the dashboard at http://localhost:8080 — within a couple of
   seconds the intersection card should light up with a signal decision
   pushed live over WebSocket, plus a live annotated-frame preview with
   detection boxes drawn on it.

## Choosing a detector (camera-ingestion-service)

Set `DETECTOR` in `camera-ingestion-service/.env` (or the compose
environment):

- `mock` (default) — deterministic fake counts + boxes, zero extra install.
  Use this for the two-laptop demo unless you specifically need real vision.
- `yolo` — real detection via YOLOv8n. Lightweight, CPU-friendly. Uncomment
  its deps in `camera-ingestion-service/requirements.txt` first.
- `rtdetr` — real detection via RT-DETR (transformer-based). Handles dense/
  overlapping high-resolution traffic better than YOLO, but is a heavy
  install (~2-4GB, torch + transformers) and needs a GPU for real-time
  performance — on CPU alone expect low single-digit FPS. Uncomment its deps
  first, and read the docstring at the top of
  `camera-ingestion-service/app/detector.py` before enabling it on a laptop.
  Also note: like YOLO, standard RT-DETR checkpoints have no "ambulance"
  class — use `emergency_override` for that case regardless of detector.

No camera hardware yet? Skip straight to step 3's cause by posting directly
to the signal service's synchronous endpoint (`/infer/signal-decision`, see
`signal-service/README`/`contracts/openapi/signal-service-api.yaml`) or the backend's
`/traffic-events` endpoint.

## Redis channels (for debugging with `redis-cli`)

```
vectra.traffic.detection   # camera-ingestion-service -> signal-service
vectra.signal.decision     # signal-service -> backend -> dashboard
vectra.incident.report     # signal-service/backend -> police-case-service
```

```bash
docker compose exec redis redis-cli subscribe vectra.signal.decision
```

## Individual services without Docker

Each service also has its own `.env.example` and can run with
`uvicorn app.main:app --reload` directly — see the comments at the top of
each service's `requirements.txt`/`Dockerfile`. Useful for the "signal service on
a separate laptop" testing flow.

## Tearing down

```bash
docker compose down        # stop, keep data
docker compose down -v     # stop and wipe Postgres/MinIO volumes
# or: make clean
```
