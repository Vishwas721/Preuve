"""arq worker entrypoint: `uv run arq app.workers.settings.WorkerSettings`."""

from arq import cron

from app.core.config import get_settings
from app.core.observability import configure_logging, init_sentry
from app.workers.jobs import (
    analyze_interview,
    analyze_response,
    draft_outreach,
    imap_poll,
    interview_guide,
    ping,
    purge_page_text,
    run_analysis,
    send_campaign,
    validation_report,
    verify_research_import,
)
from app.workers.queue import redis_settings

_settings = get_settings()
configure_logging(_settings.log_format, _settings.log_level)
init_sentry(_settings.sentry_dsn, _settings.environment, "worker")


class WorkerSettings:
    functions = [
        ping,
        run_analysis,
        verify_research_import,
        draft_outreach,
        send_campaign,
        analyze_response,
        imap_poll,
        interview_guide,
        analyze_interview,
        validation_report,
        purge_page_text,
    ]
    # Poll the mailbox every IMAP_POLL_MINUTES (the job returns at once if IMAP is off).
    cron_jobs = [
        cron(
            imap_poll,
            minute=set(range(0, 60, max(1, get_settings().imap_poll_minutes))),
            run_at_startup=False,
        ),
        # Retention (Phase 5B): once a day, early morning.
        cron(purge_page_text, hour={4}, minute={15}, run_at_startup=False),
    ]
    redis_settings = redis_settings()
    max_jobs = 10
    job_timeout = 600  # research jobs can be slow
    keep_result = 3600
