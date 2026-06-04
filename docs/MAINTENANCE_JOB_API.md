# Maintenance Job API

The maintenance job API runs long scripts through the backend and stores job
metadata/logs under runtime storage:

```text
%BASE_DIR%\data\jobs\{job_id}.json
%BASE_DIR%\data\jobs\{job_id}.log
```

Use this API for desktop tooling and future React maintenance screens. Do not
call destructive scripts directly from the frontend.

## Endpoints

```text
GET  /api/tools/jobs
GET  /api/tools/jobs/{job_id}
GET  /api/tools/jobs/{job_id}/logs
POST /api/tools/jobs/{job_type}
POST /api/tools/jobs/{job_id}/cancel
```

Supported job types:

```text
build_index
repair_empty_actor_photos
cleanup_actors
cleanup_empty_actor_dirs
cleanup_images
scrape_stashdb
```

## Job Fields

Each job returns:

```json
{
  "id": "389857c28e294efd9fd03f037866306a",
  "type": "cleanup_actors",
  "status": "completed",
  "created_at": 1780610000.0,
  "started_at": 1780610000.1,
  "finished_at": 1780610001.2,
  "progress": null,
  "exit_code": 0,
  "command": ["python", "scripts/cleanup_actors.py"],
  "dry_run": true,
  "log_path": "D:\\FaceService\\data\\jobs\\389857c28e294efd9fd03f037866306a.log",
  "error": null,
  "heavy": true
}
```

Statuses:

```text
queued
running
cancelling
completed
failed
cancelled
```

## Dry-Run By Default

Most jobs are dry-run by default:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_actors `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--require-image\",\"--include-unknown\"]}"
```

Apply mode must be explicit:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_actors `
  -H "Content-Type: application/json" `
  -d "{\"apply\":true,\"args\":[\"--require-image\",\"--include-unknown\"]}"
```

`build_index` is the exception: rebuilding the FAISS index always writes index
files, so the job is marked `writes_without_apply`.

## Common Examples

List jobs and supported job types:

```powershell
curl.exe http://127.0.0.1:8000/api/tools/jobs
```

Read one job:

```powershell
curl.exe http://127.0.0.1:8000/api/tools/jobs/JOB_ID
```

Read job logs:

```powershell
curl.exe "http://127.0.0.1:8000/api/tools/jobs/JOB_ID/logs?tail_bytes=4000"
```

Cancel a running job:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/JOB_ID/cancel
```

Rebuild FAISS index:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/build_index `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--min-images\",\"4\"]}"
```

Repair actors that have no local photos, dry-run:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/repair_empty_actor_photos `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--limit\",\"10\",\"--delay\",\"0\"]}"
```

Repair actors and write changes:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/repair_empty_actor_photos `
  -H "Content-Type: application/json" `
  -d "{\"apply\":true,\"args\":[\"--limit\",\"10\",\"--delay\",\"0\",\"--build-index-args\",\"--min-images 4\"]}"
```

Cleanup empty actor folders, dry-run:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_empty_actor_dirs `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--without-images\"]}"
```

Cleanup bad actor images, dry-run:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_images `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--min-face-area-ratio\",\"0.01\",\"--delete-missing\"]}"
```

Scrape StashDB in dry-run mode:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/scrape_stashdb `
  -H "Content-Type: application/json" `
  -d "{\"args\":[\"--limit\",\"20\",\"--require-image\"]}"
```

Scrape StashDB and write changes:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/scrape_stashdb `
  -H "Content-Type: application/json" `
  -d "{\"apply\":true,\"args\":[\"--limit\",\"20\",\"--require-image\",\"--image-count\",\"3\"]}"
```

## Notes For UI

- Poll `GET /api/tools/jobs/{job_id}` while a job is running.
- Poll `GET /api/tools/jobs/{job_id}/logs?tail_bytes=...` for live logs.
- Show `dry_run` clearly before enabling any destructive apply action.
- Treat `build_index` as destructive to index files even though it does not use
  `apply`.
- Show `error` and non-zero `exit_code` in the UI.
- Disable starting a second heavy job when the API returns `409`.
