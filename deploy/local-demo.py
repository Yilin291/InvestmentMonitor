"""Local convenience runner. Generates ephemeral local-only auth; never prints secrets."""
import os
import secrets
from pathlib import Path
from backend.serve import main

root=Path(__file__).resolve().parent.parent
os.environ.setdefault('DEMO_PASSWORD',secrets.token_urlsafe(32))
os.environ.setdefault('SESSION_SECRET',secrets.token_urlsafe(32))
os.environ.setdefault('TICK_SECRET',secrets.token_urlsafe(32))
# Optional password file for local operator; not tracked, never included in reports.
credentials=root/'.product-data'/'local-credentials.json'
credentials.parent.mkdir(exist_ok=True)
import json
fd=os.open(credentials,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:json.dump({k:os.environ[k] for k in ('DEMO_PASSWORD','SESSION_SECRET','TICK_SECRET')},f)
main()
