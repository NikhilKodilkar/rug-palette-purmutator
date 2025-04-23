# Implementation Plan

> **Road‑map with vibe‑coding phases.** Each phase is deployable & adds user value.

## Phase 1 – MVP (Weeks 0‑2)
| Task | Owner | Notes |
|------|-------|-------|
| Repo + Docker skeleton | Dev Lead | `frontend/`, `api/`, `cv-service/` |
| File upload UI | FE | React‑Dropzone → Node `/upload` |
| Scanner animation | FE | Framer‑Motion, fake 1 s delay |
| Python `segment` endpoint | CV | SAM masks + k‑means palette JSON |
| Palette + mask preview | FE | Show overlays, allow shade merge |
| Save meta to SQLite | BE | `uploads`, `masks`, `palette` tables |
| Smoke tests & CI | DevOps | GH Actions + pre‑commit |

✅ Exit criteria: User can upload a rug, see its colour segments, merge similar shades, and view the extracted palette.

---

## Phase 2 – Single Permutation (Weeks 3‑4)
| Task | Owner | Notes |
|------|-------|-------|
| Colour‑picker UI (5 inputs) | FE | React‑Colorful |
| `/recolour?perm=0` endpoint | CV | Replace colours mask‑wise |
| Progress websocket | BE | Job updates 0 → 100 % |
| Thumbnail viewer | FE | React‑Three grid |
| Star / Save buttons | FE/BE | Save refs to SQLite |

✅ Exit criteria: User supplies new palette, generates **1** natural recolour, can star or save.

---

## Phase 3 – Full Permutations (Weeks 5‑6)
| Task | Owner | Notes |
|------|-------|-------|
| Permutation generator (120 jobs) | BE | BullMQ fan‑out |
| Priority queue (first 20) | BE | Fast feedback UX |
| Batch websocket stream | BE | Emit each ready thumb |
| Pagination & filter (starred) | FE | Zustand store + tabs |
| Hide/Show segmentation | FE | Shader toggle |
| Download zip of stars | BE | On‑the‑fly zip stream |
| Prod deploy + docs | DevOps | Fly.io with GPU plan |

✅ Exit criteria: Full 120 permutations stream back, UX smooth, starred rugs downloadable.

---

## Future (Back‑burner)
- Auth & multi‑user workspaces
- S3 off‑load & CDN thumbs
- Fine‑tune LoRA for exotic textures
- Mobile‑first PWA
- Paywall for bulk exports

