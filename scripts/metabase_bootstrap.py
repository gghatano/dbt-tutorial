#!/usr/bin/env python3
"""
Metabase bootstrap (idempotent).

Creates / ensures:
  - admin user (via Setup API on first run, login fallback otherwise)
  - Postgres data source (`local-analytics`, connecting as readonly_user)
  - Collection `Sales Marts`
  - 3 saved questions (Daily Sales / Top 20 Customers / Sales by Category)
  - Dashboard `Sales Overview` with the 3 cards laid out

Re-running is safe: items are upserted by name, no duplicates.

Usage:
    .venv/bin/python scripts/metabase_bootstrap.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env", override=True)

BASE = os.environ.get("METABASE_URL", "http://localhost:3000").rstrip("/")
ADMIN_EMAIL = os.environ["METABASE_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["METABASE_ADMIN_PASSWORD"]
ADMIN_FIRST = os.environ.get("METABASE_ADMIN_FIRST", "Local")
ADMIN_LAST = os.environ.get("METABASE_ADMIN_LAST", "Admin")
SITE_NAME = os.environ.get("METABASE_SITE_NAME", "local-data-platform")
SITE_LOCALE = os.environ.get("METABASE_SITE_LOCALE", "ja")

DB_NAME = os.environ.get("METABASE_DB_NAME", "local-analytics")
DB_RO_USER = os.environ.get("METABASE_DB_RO_USER", "readonly_user")
DB_RO_PASSWORD = os.environ["METABASE_DB_RO_PASSWORD"]
# Inside the docker network the postgres host is `postgres` (compose service name).
DB_HOST_INTERNAL = os.environ.get("METABASE_DB_HOST", "postgres")
DB_PORT = int(os.environ.get("METABASE_DB_PORT", "5432"))
DB_DBNAME = os.environ.get("METABASE_DB_DBNAME", "analytics")

COLLECTION_NAME = "Sales Marts"
DASHBOARD_NAME = "Sales Overview"
TIMEOUT = 10

session = requests.Session()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(step: str, status: str = "OK", extra: str = "") -> None:
    msg = f"[bootstrap] {step} ... {status}"
    if extra:
        msg += f" ({extra})"
    print(msg, flush=True)


def fail(step: str, resp: requests.Response) -> None:
    raise SystemExit(
        f"[bootstrap] {step} FAILED: HTTP {resp.status_code}\n{resp.text}"
    )


def _check(resp: requests.Response, step: str) -> requests.Response:
    if not resp.ok:
        fail(step, resp)
    return resp


def get(path: str, **kw: Any) -> requests.Response:
    return session.get(f"{BASE}{path}", timeout=TIMEOUT, **kw)


def post(path: str, json: Any = None, **kw: Any) -> requests.Response:
    return session.post(f"{BASE}{path}", json=json, timeout=TIMEOUT, **kw)


def put(path: str, json: Any = None, **kw: Any) -> requests.Response:
    return session.put(f"{BASE}{path}", json=json, timeout=TIMEOUT, **kw)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def wait_for_health(max_seconds: int = 120) -> None:
    deadline = time.time() + max_seconds
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            r = get("/api/health")
            if r.ok and r.json().get("status") == "ok":
                log("health check")
                return
        except Exception as e:  # pragma: no cover - transport errors
            last_err = e
        time.sleep(2)
    raise SystemExit(
        f"[bootstrap] health check FAILED after {max_seconds}s: {last_err}"
    )


def get_setup_token() -> Optional[str]:
    """Return the one-shot setup token *only* if the instance hasn't been
    initialized yet.

    Note: Metabase keeps `setup-token` populated in /api/session/properties
    even after setup completes, but the token is rejected by /api/setup once
    a user exists. The reliable "first run" signal is `has-user-setup=False`.
    """
    r = _check(get("/api/session/properties"), "session properties")
    body = r.json()
    if body.get("has-user-setup"):
        return None
    return body.get("setup-token")


def db_engine_payload(name: str) -> dict:
    return {
        "name": name,
        "engine": "postgres",
        "details": {
            "host": DB_HOST_INTERNAL,
            "port": DB_PORT,
            "dbname": DB_DBNAME,
            "user": DB_RO_USER,
            "password": DB_RO_PASSWORD,
            "ssl": False,
            "tunnel-enabled": False,
        },
    }


def setup_first_run(token: str) -> tuple[int, int]:
    """Run /api/setup. Returns (database_id, user_id)."""
    payload = {
        "token": token,
        "user": {
            "first_name": ADMIN_FIRST,
            "last_name": ADMIN_LAST,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "site_name": SITE_NAME,
        },
        "database": db_engine_payload(DB_NAME),
        "prefs": {
            "site_name": SITE_NAME,
            "site_locale": SITE_LOCALE,
            "allow_tracking": False,
        },
    }
    r = _check(post("/api/setup", json=payload), "setup")
    data = r.json()
    metabase_session = data.get("id")
    if not metabase_session:
        # Older API shapes return the session via cookie; fetch it via login.
        metabase_session = login_get_session_id()
    session.headers["X-Metabase-Session"] = metabase_session
    log("setup (admin + db created)")
    # We don't get the database id back from /api/setup, look it up.
    db_id = ensure_database()
    return db_id, 0


def login_get_session_id() -> str:
    r = _check(
        post(
            "/api/session",
            json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        ),
        "login",
    )
    return r.json()["id"]


def login_existing() -> None:
    sid = login_get_session_id()
    session.headers["X-Metabase-Session"] = sid
    log("admin login")


def ensure_database() -> int:
    """Find DB by name; create it if missing. Returns its id."""
    r = _check(get("/api/database"), "list databases")
    body = r.json()
    items = body.get("data", body) if isinstance(body, dict) else body
    for db in items:
        if db.get("name") == DB_NAME and db.get("engine") == "postgres":
            log("database ensure", "SKIP", f"id={db['id']}")
            return int(db["id"])
    r = _check(post("/api/database", json=db_engine_payload(DB_NAME)), "create database")
    db_id = int(r.json()["id"])
    log("database ensure", "OK", f"id={db_id}")
    return db_id


def sync_schema(db_id: int) -> None:
    _check(post(f"/api/database/{db_id}/sync_schema"), "sync_schema")
    # Wait until marts tables show up in the metadata.
    deadline = time.time() + 60
    while time.time() < deadline:
        r = get(f"/api/database/{db_id}/metadata")
        if r.ok:
            tables = r.json().get("tables", []) or []
            mart_tables = [
                t for t in tables
                if (t.get("schema") == "marts")
                and t.get("name", "").startswith("mart_")
            ]
            if len(mart_tables) >= 3:
                log(
                    "schema sync",
                    "OK",
                    f"{len(mart_tables)} marts tables visible",
                )
                return
        time.sleep(2)
    log("schema sync", "WARN", "marts not yet visible (continuing)")


def find_collection(name: str) -> Optional[dict]:
    r = _check(get("/api/collection"), "list collections")
    for c in r.json():
        if c.get("name") == name and not c.get("archived"):
            return c
    return None


def ensure_collection() -> int:
    existing = find_collection(COLLECTION_NAME)
    if existing:
        log("collection ensure", "SKIP", f"id={existing['id']}")
        return int(existing["id"])
    r = _check(
        post(
            "/api/collection",
            json={
                "name": COLLECTION_NAME,
                "description": "dbt marts visualizations (auto-bootstrapped).",
                "color": "#509EE3",
                "parent_id": None,
            },
        ),
        "create collection",
    )
    cid = int(r.json()["id"])
    log("collection ensure", "OK", f"id={cid}")
    return cid


# Card definitions ----------------------------------------------------------

def card_specs(db_id: int) -> list[dict]:
    return [
        {
            "name": "Daily Sales",
            "display": "line",
            "sql": (
                "select order_date, total_sales_amount "
                "from marts.mart_daily_sales order by order_date"
            ),
            "visualization_settings": {
                "graph.dimensions": ["order_date"],
                "graph.metrics": ["total_sales_amount"],
                "graph.x_axis.title_text": "Order date",
                "graph.y_axis.title_text": "Total sales",
            },
        },
        {
            "name": "Top 20 Customers",
            "display": "bar",
            "sql": (
                "select customer_name, total_sales_amount "
                "from marts.mart_customer_sales "
                "order by total_sales_amount desc limit 20"
            ),
            "visualization_settings": {
                "graph.dimensions": ["customer_name"],
                "graph.metrics": ["total_sales_amount"],
                "graph.x_axis.title_text": "Customer",
                "graph.y_axis.title_text": "Total sales",
            },
        },
        {
            "name": "Sales by Category",
            "display": "pie",
            "sql": (
                "select category, sum(total_sales_amount) as total "
                "from marts.mart_product_sales "
                "group by category order by total desc"
            ),
            "visualization_settings": {
                "pie.dimension": "category",
                "pie.metric": "total",
            },
        },
    ]


def card_payload(spec: dict, db_id: int, collection_id: int) -> dict:
    return {
        "name": spec["name"],
        "display": spec["display"],
        "visualization_settings": spec["visualization_settings"],
        "dataset_query": {
            "type": "native",
            "database": db_id,
            "native": {"query": spec["sql"]},
        },
        "collection_id": collection_id,
    }


def list_cards() -> list[dict]:
    r = _check(get("/api/card"), "list cards")
    body = r.json()
    if isinstance(body, dict):
        return body.get("data", []) or []
    return body or []


def ensure_card(spec: dict, db_id: int, collection_id: int) -> int:
    payload = card_payload(spec, db_id, collection_id)
    existing = next(
        (
            c for c in list_cards()
            if c.get("name") == spec["name"] and not c.get("archived")
        ),
        None,
    )
    if existing:
        cid = int(existing["id"])
        # Update so the SQL/viz settings always match the source of truth.
        update = {
            "display": payload["display"],
            "visualization_settings": payload["visualization_settings"],
            "dataset_query": payload["dataset_query"],
            "collection_id": collection_id,
        }
        _check(put(f"/api/card/{cid}", json=update), f"update card {spec['name']}")
        log(f"card '{spec['name']}'", "SKIP", f"id={cid} (updated)")
        return cid
    r = _check(post("/api/card", json=payload), f"create card {spec['name']}")
    cid = int(r.json()["id"])
    log(f"card '{spec['name']}'", "OK", f"id={cid}")
    return cid


def find_dashboard(name: str) -> Optional[dict]:
    r = _check(get("/api/dashboard"), "list dashboards")
    body = r.json()
    items = body.get("data", body) if isinstance(body, dict) else body
    for d in items:
        if d.get("name") == name and not d.get("archived"):
            return d
    return None


def ensure_dashboard(collection_id: int) -> int:
    existing = find_dashboard(DASHBOARD_NAME)
    if existing:
        log("dashboard ensure", "SKIP", f"id={existing['id']}")
        return int(existing["id"])
    r = _check(
        post(
            "/api/dashboard",
            json={
                "name": DASHBOARD_NAME,
                "description": "dbt marts overview (auto-bootstrapped).",
                "collection_id": collection_id,
            },
        ),
        "create dashboard",
    )
    did = int(r.json()["id"])
    log("dashboard ensure", "OK", f"id={did}")
    return did


def get_dashboard(dashboard_id: int) -> dict:
    r = _check(get(f"/api/dashboard/{dashboard_id}"), "fetch dashboard")
    return r.json()


def attach_cards(dashboard_id: int, card_ids: list[int]) -> None:
    """Place the 3 cards. 2 columns x ~6x6 each."""
    layout = [
        # (col, row, size_x, size_y)
        (0, 0, 12, 6),  # Daily Sales (full width top)
        (0, 6, 6, 6),   # Top customers
        (6, 6, 6, 6),   # Sales by category
    ]
    dash = get_dashboard(dashboard_id)
    existing_dashcards = dash.get("dashcards") or dash.get("ordered_cards") or []
    existing_card_ids = {dc.get("card_id") for dc in existing_dashcards}

    # Skip if every card is already on the dashboard.
    if all(cid in existing_card_ids for cid in card_ids):
        log("dashcards attach", "SKIP", f"{len(existing_dashcards)} dashcards present")
        return

    # Construct the full dashcards payload (Metabase replaces all on PUT).
    dashcards = []
    for idx, (cid, (col, row, sx, sy)) in enumerate(zip(card_ids, layout)):
        dashcards.append({
            "id": -(idx + 1),  # negative ids = new
            "card_id": cid,
            "col": col,
            "row": row,
            "size_x": sx,
            "size_y": sy,
            "parameter_mappings": [],
            "visualization_settings": {},
        })
    _check(
        put(
            f"/api/dashboard/{dashboard_id}",
            json={"dashcards": dashcards},
        ),
        "attach dashcards",
    )
    log("dashcards attach", "OK", f"{len(dashcards)} cards placed")


def verify_dashboard(dashboard_id: int, expected_card_ids: list[int]) -> None:
    dash = get_dashboard(dashboard_id)
    dcs = dash.get("dashcards") or dash.get("ordered_cards") or []
    found = {dc.get("card_id") for dc in dcs}
    missing = [c for c in expected_card_ids if c not in found]
    if missing:
        raise SystemExit(
            f"[bootstrap] verify FAILED: missing card ids on dashboard: {missing}"
        )
    log("verify dashboard", "OK", f"{len(dcs)} dashcards, all expected cards present")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[bootstrap] Metabase URL: {BASE}")
    wait_for_health()

    token = get_setup_token()
    if token:
        log("setup-token detected", "OK", "first-run path")
        db_id, _ = setup_first_run(token)
    else:
        log("setup-token detected", "SKIP", "already initialized")
        login_existing()
        db_id = ensure_database()

    sync_schema(db_id)

    collection_id = ensure_collection()

    specs = card_specs(db_id)
    card_ids = [ensure_card(s, db_id, collection_id) for s in specs]

    dashboard_id = ensure_dashboard(collection_id)
    attach_cards(dashboard_id, card_ids)
    verify_dashboard(dashboard_id, card_ids)

    print()
    print("=" * 60)
    print("Metabase bootstrap complete.")
    print(f"  Dashboard URL : {BASE}/dashboard/{dashboard_id}")
    print(f"  Admin email   : {ADMIN_EMAIL}")
    print(f"  Admin password: {ADMIN_PASSWORD}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        print(f"[bootstrap] network error: {e}", file=sys.stderr)
        sys.exit(1)
