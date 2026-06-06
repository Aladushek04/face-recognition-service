import multiprocessing
import os
import sys
import uvicorn

ALLOWED_JOBS = {
    "cleanup_actors": "jobs.cleanup_actors",
    "cleanup_empty_actor_dirs": "jobs.cleanup_empty_actor_dirs",
    "cleanup_images": "jobs.cleanup_images",
    "repair_empty_actor_photos": "jobs.repair_empty_actor_photos",
    "scrape_stashdb": "jobs.scrape_stashdb",
    "build_index": "jobs.build_index",
}


def _run_job_from_args() -> None:
    job_name = sys.argv[2]
    job_args = sys.argv[3:]

    if job_name not in ALLOWED_JOBS:
        print(f"ERROR: Unknown or unauthorized job '{job_name}'", file=sys.stderr)
        sys.exit(1)

    import importlib
    try:
        module = importlib.import_module(ALLOWED_JOBS[job_name])
        exit_code = module.main(job_args)
        sys.exit(exit_code)
    except Exception as e:
        print(f"ERROR: Failed to run job '{job_name}': {e}", file=sys.stderr)
        sys.exit(1)

# Important: freeze_support MUST be called immediately in __main__
if __name__ == "__main__":
    multiprocessing.freeze_support()

    if len(sys.argv) >= 3 and sys.argv[1] == "--run-job":
        _run_job_from_args()

    from main import app

    if hasattr(sys, '_MEIPASS'):
        os.add_dll_directory(sys._MEIPASS)
        os.add_dll_directory(os.path.dirname(sys.executable))
        
    host = os.environ.get("HOST", "127.0.0.1")
    port_str = os.environ.get("PORT", "52800")
    try:
        port = int(port_str)
    except ValueError:
        port = 52800

    # Explicitly run without reload to prevent Uvicorn from forking
    uvicorn.run(app, host=host, port=port, log_level="info", workers=1)
