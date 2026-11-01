"""arq worker entrypoint: `uv run arq app.workers.settings.WorkerSettings`."""

from app.workers.jobs import ping, run_analysis, verify_research_import
from app.workers.queue import redis_settings


class WorkerSettings:
    functions = [ping, run_analysis, verify_research_import]
    redis_settings = redis_settings()
    max_jobs = 10
    job_timeout = 600  # research jobs can be slow
    keep_result = 3600
