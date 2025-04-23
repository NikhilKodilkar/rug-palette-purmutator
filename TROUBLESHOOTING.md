# Troubleshooting Log (TS.md)
Keep this file **chronological**. Every bug gets:
```
### [yyyymmdd‑hhmm] <short‑title>
**Symptom:**  _what broke_
**Root‑cause:** _why_
**Fix:**  _commit hash / steps_
```

---

### Template sections
- **Build / Docker**
- **Front‑end** (React/Vite)
- **API** (Node)
- **CV‑Service** (Python)
- **Database / Migrations**
- **DevOps / CI**

---

#### [20250422‑init] Initial placeholders
**Symptom:** No CI pipeline.
**Root‑cause:** Greenfield repo.
**Fix:** Added GH‑Actions workflow `ci.yml` (lint+test+build).

#### [20250422‑cors‑cv] CORS error calling Python service
**Symptom:** `Access‑Control‑Allow‑Origin` missing on `/segment`.
**Root‑cause:** FastAPI default CORS policy.
**Fix:** Enabled `CORSMiddleware` with frontend origin in `main.py`.

