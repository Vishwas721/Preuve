from functools import lru_cache

from app.core.config import get_settings
from app.email.base import EmailProvider
from app.email.smtp import SmtpProvider


@lru_cache
def get_email_provider() -> EmailProvider:
    s = get_settings()
    return SmtpProvider(
        s.smtp_host,
        s.smtp_port,
        username=s.smtp_username,
        password=s.smtp_password,
        starttls=s.smtp_starttls,
        ssl=s.smtp_ssl,
        timeout_s=s.smtp_timeout_s,
    )
