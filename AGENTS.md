# Codex Project Context

Before desktop migration, maintenance tooling, packaging, or script orchestration
work, read `DESKTOP_MIGRATION_PLAN.md`.

Project priorities:

1. Stability and recoverability before visual polish.
2. Browser-local mode must keep working.
3. Use backend APIs and job orchestration for long-running tasks.
4. Keep destructive actions behind dry-run/apply confirmation.
5. Do not commit heavy runtime data, actor databases, actor photos, videos,
   embeddings, FAISS indexes, thumbnails, uploads, or downloaded ML models.
6. Keep desktop shell replaceable. React and FastAPI should not depend on
   Electron-specific APIs.

Verification defaults:

- `python -m compileall backend scripts`
- `npm run build` from `frontend`

