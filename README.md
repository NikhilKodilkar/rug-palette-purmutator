# Rug Palette Permutator

## Overview

Re‑colour any rug photograph with a brand‑new 5‑colour palette and keep the fabric texture looking natural. The system:

1. Accepts an image upload.
2. Segments the rug using Meta AI's Segment Anything model.
3. Allows the user to interactively regroup similar colour segments via the UI.
4. Accepts a new 5-colour palette via a colour picker UI component.
5. Generates up to **120** realistic permutations using LAB histogram matching (fast preview) and optional pyramid blending (high-quality zoom/export).

## Tech Stack

| Layer                | Tech                                                                          | Reason                                                                 |
| -------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Front‑end**        | React 18 (+ Vite) · Zustand · React‑Three‑Fiber · Framer‑Motion               | Snappy SPA, simple global state, WebGL grid & fancy scanner animation  |
| **Orchestrator API** | Node JS 20 · Express · Socket.IO · SQLite (via better‑sqlite3) · BullMQ/Redis | JS‑friendly routing, WebSockets for live progress, tiny DB & job queue |
| **CV Micro‑service** | Python 3.11 · FastAPI · PyTorch (Segment Anything) · scikit‑image             | Best CV libs; isolated GPU container                                   |
| **Deployment**       | Docker‑compose (frontend, api, python‑cv, redis)                              | One‑command spin‑up; shared `/media` volume                            |

## Architecture (Option B)

```
[React SPA] ⇆ ws/http ⇆ [Node API] → Redis (queue) → [Python CV] → /media
                                    ↘ SQLite
```

- Node handles auth, uploads, websocket streams.
- Python only runs heavy segmentation & recolour.
- Files live on a shared volume so no copies.

## Local Run

```bash
git clone https://github.com/yourorg/rug-permutator
cd rug-permutator
cp .env.example .env  # set paths & ports
docker compose up --build
```

Visit [**http://localhost:5173**](http://localhost:5173).

## Repo Structure

```
/ frontend   – React SPA
/ api        – Node orchestration server
/ cv-service – FastAPI + ML models
/docker      – compose & Dockerfiles
/media       – user images & outputs (shared)
```

## Design Decisions

Based on initial analysis, the following implementation details were clarified:

1.  **Segmentation Approach:**
    *   Use Meta AI's Segment Anything (SAM) in "everything" mode.
    *   Filter the resulting masks by area and aspect ratio to find the primary rug silhouette.
    *   Optionally dilate/erode the silhouette mask to capture edges/fringes.
    *   Run K-Means (k=5) clustering *only* on the pixels *within* the final silhouette mask (in LAB colour space). This yields the initial 5 dominant colours (centroids) and a per-pixel label map.

2.  **Interactive Segment Merging:**
    *   Merging happens in the UI first (pure state change).
    *   The UI sends a `mergeMap` (e.g., `{ oldLabel: newLabel, ... }`) to the Node API.
    *   Node persists this `mergeMap` to SQLite, associated with the upload ID.
    *   Subsequent recolour requests to the Python service include the *current* `mergeMap`.
    *   Python applies the merge logic *statelessly* by combining the original K-Means masks based on the `mergeMap` just before recolouring. It does *not* modify the original masks.
    *   The target palette provided by the user remains fixed; merging affects which *source* pixels map to which *target* colour.

3.  **Recolouring Techniques & Trigger:**
    *   **Default (Fast Preview):** LAB Histogram Matching is applied per merged segment. This is used for initial thumbnail generation and hover previews.
    *   **High Quality (Zoom/Export):** Laplacian Pyramid Blending is used for a more seamless result.
    *   **Trigger:** The frontend explicitly requests the high-quality version via a URL parameter (`GET /recolour?id=...&perm=...&quality=hi`).
        *   Low-quality requests return the image directly (or 404 if not cached).
        *   High-quality requests enqueue a job in the Python service if the result isn't cached, return a `202 Accepted` with a `jobId`, and stream progress via WebSockets. The frontend listens for the `completed` event to display the result.

4.  **Palette Input:**
    *   A standard colour picker UI component will be used for the user to define the 5 target colours.

## Contributing

- Use **Conventional Commits**.
- All TS/JS code passes `eslint --fix` & `prettier`.
- Python code is black‑formatted + mypy‑typed.

## License
Nikhil's brain
