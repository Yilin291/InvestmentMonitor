#!/usr/bin/env python3
"""Securely import provider credentials into ignored local .env.local."""

from getpass import getpass
from pathlib import Path
import os
import shlex
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env.local"
KEYS = ("FUYAO_API_KEY", "DEEPSEEK_API_KEY")


def main() -> None:
    if TARGET.exists():
        raise SystemExit(".env.local already exists; refusing to overwrite it")
    values = {}
    for name in KEYS:
        value = getpass(f"{name} (input hidden; blank to skip): ").strip()
        if value:
            confirm = getpass(f"Repeat {name} (input hidden): ").strip()
            if value != confirm:
                raise SystemExit(f"{name} confirmation did not match; no file written")
            values[name] = value
    if not values:
        raise SystemExit("No values entered; no file written")

    content = "".join(f"export {name}={shlex.quote(value)}\n" for name, value in values.items())
    fd, temp_name = tempfile.mkstemp(prefix=".env.local.", dir=ROOT, text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp_name, TARGET)
        os.chmod(TARGET, 0o600)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

    print("Wrote .env.local with mode 0600; values were not displayed.")
    print("Configured: " + ", ".join(values))


if __name__ == "__main__":
    main()
