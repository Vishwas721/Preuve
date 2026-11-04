from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)  # lower-cased
    name: Mapped[str] = mapped_column(String(200))
    # argon2id hash; None until the account is claimed (the pre-5A dev user) or set up.
    password_hash: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The account that ran first-run setup; the only one that can create password-reset links.
    is_instance_owner: Mapped[bool] = mapped_column(default=False, server_default="false")
