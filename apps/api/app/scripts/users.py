"""Account admin for the instance owner (Phase 5A).

  uv run python -m app.scripts.users reset-password <email>    # prompts for the new password
  echo "<password>" | uv run python -m app.scripts.users reset-password <email> --stdin

Sets the password and signs that user out everywhere. There's no email-based reset yet (5C).
"""

import argparse
import asyncio
import getpass
import sys

import app.db.models  # noqa: F401  (register every ORM mapper)
from app.db.session import SessionLocal
from app.modules.auth import service as auth
from app.modules.auth.security import WeakPasswordError


async def reset_password(email: str, password: str) -> str:
    async with SessionLocal() as session:
        user = await auth.set_password(session, email, password)
        return user.email


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.scripts.users")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("reset-password", help="Set a user's password and end their sessions")
    p.add_argument("email")
    p.add_argument("--stdin", action="store_true", help="Read the new password from stdin")
    args = parser.parse_args()

    if args.stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Again: "):
            sys.exit("The passwords don't match.")
    try:
        email = asyncio.run(reset_password(args.email, password))
    except (auth.AuthError, WeakPasswordError) as exc:
        sys.exit(str(exc))
    print(f"Password set for {email}; their sessions were ended.")


if __name__ == "__main__":
    main()
