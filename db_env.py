"""Central DB credential loader (JSON-backed).

Credentials live in the repo-root db_credentials.json — one object per tenant,
using the same columns as the master sheet:
    slaveUrl, slaveSchema, slaveDbPassword, slaveDBUsername

Usage from any script:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[N]))  # N = depth to repo root
    from db_env import get_db_config

    DB_CONFIG = get_db_config("collpoll_sgbs")   # just pass the tenant schema name
"""

import json
from pathlib import Path

_CRED_FILE = Path(__file__).resolve().parent / "db_credentials.json"

with open(_CRED_FILE, encoding="utf-8") as _f:
    _ROWS = json.load(_f)

# Index by schema (tenant database name) for O(1) lookup.
_BY_SCHEMA = {row["slaveSchema"]: row for row in _ROWS}


def list_schemas() -> list:
    """All known tenant schema names, sorted."""
    return sorted(_BY_SCHEMA)


def get_db_config(database: str) -> dict:
    """Return {host, user, password, database} for a tenant schema name.

    Accepts the full schema ("collpoll_sgbs") or the short form ("sgbs").
    The matching row from db_credentials.json supplies host/user/password.
    Raises KeyError with a clear message if the schema has no entry.
    """
    name = (database or "").strip()
    row = _BY_SCHEMA.get(name) or _BY_SCHEMA.get(f"collpoll_{name}")
    if row is None:
        raise KeyError(
            f"No credentials for schema '{database}' in {_CRED_FILE.name}. "
            f"Known schemas: {', '.join(list_schemas())}"
        )
    return {
        "host": row["slaveUrl"],
        "user": row["slaveDBUsername"],
        "password": row["slaveDbPassword"],
        "database": row["slaveSchema"],
    }
