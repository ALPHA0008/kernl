"""Apply backend/schema.sql to the configured Postgres database.

Usage:
    py -3 backend/apply_schema.py [--schema public] [--url postgresql://...]

Connection resolution order: --url flag, KERNL_DB_URL, SUPABASE_DB_URL
(from the environment or .env). For Supabase use the DIRECT connection
string (Dashboard -> Settings -> Database -> Connection string), never the
https API URL.

The script is idempotent: schema.sql is written with IF NOT EXISTS /
CREATE OR REPLACE throughout, so re-running is safe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def resolve_url(cli_url: str | None) -> str | None:
    import os

    # explicit repo-root .env: backend/.env (legacy, VLLM-only) would
    # otherwise shadow it in dotenv's directory walk-up
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    return cli_url or os.environ.get("KERNL_DB_URL") or os.environ.get("SUPABASE_DB_URL")


def apply(url: str, schema: str = "public") -> None:
    import psycopg
    from psycopg import sql

    ddl = SCHEMA_FILE.read_text(encoding="utf-8")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            if schema != "public":
                cur.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                )
            cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            cur.execute(ddl)  # single multi-statement batch; dollar-quoting intact
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="public")
    parser.add_argument("--url", default=None, help="overrides env")
    args = parser.parse_args()

    url = resolve_url(args.url)
    if not url:
        print(
            "ERROR: no database URL. Set KERNL_DB_URL (or SUPABASE_DB_URL) in the "
            "environment/.env, or pass --url. For Supabase this is the DIRECT "
            "Postgres connection string, not the https API URL."
        )
        return 2
    apply(url, args.schema)
    print(f"schema.sql applied to schema {args.schema!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
