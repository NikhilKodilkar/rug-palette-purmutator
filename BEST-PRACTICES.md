# Best Practices

## React (+Vite)
- **Functional components + hooks** only; avoid class components.
- **Zustand slices** per domain (`uploadStore`, `paletteStore`, `uiStore`).
- Keep global state lean; prefer local component state when possible.
- Enable React 18 **Strict Mode** and **Suspense** for lazy routes.
- Use **TypeScript** (`strict` true). 100 % typed exports.
- UI‑level tests with **Vitest + React Testing Library**.
- Accessibility first: semantic HTML, alt‑text on images.
- Code splitting: `import()` grid/permutation pages so initial bundle < 150 kB.

## Next.js *(if ever adopted)*
- Use **app router** + **server actions** for royalty‑free SSR uploads.
- Keep image processing OUT of API routes; delegate to Python service.
- Turn on **static export** when only the SPA is needed.

## Node (Express + Socket.IO)
- Wrap every async route in error‑handler middleware; never `try/catch` in controllers.
- Validate request bodies with **zod** and return granular 4xx errors.
- One controller → one service; keep business logic out of routes.
- Use **BullMQ** for all long‑running jobs; acknowledge fast.
- Do not store blobs in SQLite—store **absolute file paths** only.
- Emit websocket events (`progress`, `completed`) from job hooks.

## Python (FastAPI CV service)
- Model weights are version‑pinned; specify SHA in `requirements.txt`.
- **Pydantic** models for all request/response bodies.
- All endpoints async; use non‑blocking `await` file I/O.
- Release GPU memory: `torch.cuda.empty_cache()` after job.
- Unit tests with **pytest**; fixtures include tiny 64×64 rug.
- Structured logging via **loguru**; `uvicorn --access-log` in prod.

## Shared Discipline
- One `.env` per service; never commit secrets.
- **Pre‑commit** hooks: `eslint`, `prettier`, `black`, `mypy`, `pytest -q`.
- Docker images are multi‑stage; final prod images are slim (< 300 MB).
- CI: GitHub Actions – lint, test, build images, push to registry.
- Semantic version: `MAJOR.MINOR.PATCH`; breaking API changes bump major.
- Every new bug & fix MUST be logged in **TS.md** immediately.

