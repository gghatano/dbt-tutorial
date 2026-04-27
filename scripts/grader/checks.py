"""Check implementations for the grader.

Each check is a function that takes (params, ctx) and returns CheckResult.
ctx exposes: dbt_dir (Path), repo_root (Path), manifest_json (dict|None),
db_dsn (str|None), and a small logger.

Adding a new check type
-----------------------
1. Define ``run_<type>(params, ctx) -> CheckResult`` here.
2. Register it in ``CHECK_TYPES`` at the bottom.
3. Document the YAML schema in ``docs/exercises/grading.md``.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass
class CheckResult:
    passed: bool
    message: str
    details: str = ""


@dataclass
class GraderContext:
    dbt_dir: Path
    repo_root: Path
    db_dsn: Optional[str]
    target_path: Path  # dbt/target

    def manifest(self) -> Optional[dict]:
        p = self.target_path / "manifest.json"
        if not p.exists():
            return None
        with p.open() as fh:
            return json.load(fh)


# ---------------------------------------------------------------------------
# dbt_command
# ---------------------------------------------------------------------------

def run_dbt_command(params: dict, ctx: GraderContext) -> CheckResult:
    cmd = params.get("command")
    if not cmd:
        return CheckResult(False, "command field missing")
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = list(cmd)
    if cmd_list and cmd_list[0] == "dbt":
        cmd_list = ["dbt", *cmd_list[1:], "--profiles-dir", "."]
    try:
        proc = subprocess.run(
            cmd_list,
            cwd=str(ctx.dbt_dir),
            capture_output=True,
            text=True,
            timeout=params.get("timeout_sec", 180),
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(False, "dbt command timed out", str(exc))
    except FileNotFoundError:
        return CheckResult(False, f"dbt binary not found in PATH (cmd={cmd_list[0]})")
    ok = proc.returncode == 0
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
    msg = "ok" if ok else f"exit {proc.returncode}"
    return CheckResult(ok, msg, tail)


# ---------------------------------------------------------------------------
# manifest_node_exists
# ---------------------------------------------------------------------------

def run_manifest_node_exists(params: dict, ctx: GraderContext) -> CheckResult:
    manifest = ctx.manifest()
    if manifest is None:
        return CheckResult(False, "manifest.json not found (run `dbt parse` first)")
    node = params.get("node")
    if not node:
        return CheckResult(False, "node field missing")
    pools = (
        manifest.get("nodes", {}),
        manifest.get("sources", {}),
        manifest.get("exposures", {}),
        manifest.get("snapshots", {}),
    )
    for pool in pools:
        if node in pool:
            return CheckResult(True, f"node found: {node}")
    return CheckResult(False, f"node missing: {node}")


# ---------------------------------------------------------------------------
# manifest_lineage
# ---------------------------------------------------------------------------

def run_manifest_lineage(params: dict, ctx: GraderContext) -> CheckResult:
    manifest = ctx.manifest()
    if manifest is None:
        return CheckResult(False, "manifest.json not found")
    node = params.get("node")
    if not node:
        return CheckResult(False, "node field missing")
    pools = (
        manifest.get("nodes", {}),
        manifest.get("sources", {}),
        manifest.get("exposures", {}),
        manifest.get("snapshots", {}),
    )
    found = None
    for pool in pools:
        if node in pool:
            found = pool[node]
            break
    if found is None:
        return CheckResult(False, f"node missing: {node}")
    upstream = found.get("depends_on", {}).get("nodes", [])
    upstream_min = params.get("upstream_min_count")
    if upstream_min is not None and len(upstream) < upstream_min:
        return CheckResult(
            False,
            f"upstream count {len(upstream)} < required {upstream_min}",
            "depends_on=" + ", ".join(upstream),
        )
    must_include = params.get("upstream_must_include", []) or []
    missing = [m for m in must_include if m not in upstream]
    if missing:
        return CheckResult(
            False,
            f"upstream missing required: {missing}",
            "depends_on=" + ", ".join(upstream),
        )
    return CheckResult(True, f"upstream count {len(upstream)} OK")


# ---------------------------------------------------------------------------
# manifest_config
# ---------------------------------------------------------------------------

def run_manifest_config(params: dict, ctx: GraderContext) -> CheckResult:
    manifest = ctx.manifest()
    if manifest is None:
        return CheckResult(False, "manifest.json not found")
    node = params.get("node")
    if not node:
        return CheckResult(False, "node field missing")
    pools = (
        manifest.get("nodes", {}),
        manifest.get("sources", {}),
        manifest.get("exposures", {}),
        manifest.get("snapshots", {}),
    )
    found = None
    for pool in pools:
        if node in pool:
            found = pool[node]
            break
    if found is None:
        return CheckResult(False, f"node missing: {node}")
    expected = params.get("expected", {}) or {}
    config = found.get("config", {}) or {}
    mismatches = []
    for key, want in expected.items():
        got = _dig(config, key)
        if got != want:
            mismatches.append(f"{key}: got={got!r} want={want!r}")
    if mismatches:
        return CheckResult(False, "config mismatch", "; ".join(mismatches))
    return CheckResult(True, "config OK", str(expected))


def _dig(d: dict, dotted_key: str) -> Any:
    cur: Any = d
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


# ---------------------------------------------------------------------------
# dbt_test_passes
# ---------------------------------------------------------------------------

def run_dbt_test_passes(params: dict, ctx: GraderContext) -> CheckResult:
    selector = params.get("select", "")
    cmd = ["dbt", "test", "--profiles-dir", "."]
    if selector:
        cmd += ["--select", selector]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ctx.dbt_dir),
            capture_output=True,
            text=True,
            timeout=params.get("timeout_sec", 180),
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(False, "dbt test timed out", str(exc))
    out = proc.stdout + proc.stderr
    summary = re.search(r"Done\.\s+PASS=(\d+)\s+WARN=(\d+)\s+ERROR=(\d+)\s+SKIP=(\d+)(?:\s+NO-OP=(\d+))?\s+TOTAL=(\d+)", out)
    if proc.returncode != 0 and summary is None:
        return CheckResult(False, f"dbt test exited {proc.returncode} (no summary)", _tail(out))
    if summary is None:
        return CheckResult(False, "no test summary parsed", _tail(out))
    pass_n, warn_n, err_n = int(summary.group(1)), int(summary.group(2)), int(summary.group(3))
    total = int(summary.group(6))
    expect_min_pass = params.get("min_pass", 1)
    if err_n > 0:
        return CheckResult(False, f"PASS={pass_n} WARN={warn_n} ERROR={err_n} TOTAL={total}", _tail(out))
    if pass_n < expect_min_pass:
        return CheckResult(False, f"PASS={pass_n} < expected {expect_min_pass}", _tail(out))
    return CheckResult(True, f"PASS={pass_n} WARN={warn_n} ERROR={err_n} TOTAL={total}")


# ---------------------------------------------------------------------------
# sql_assert
# ---------------------------------------------------------------------------

def run_sql_assert(params: dict, ctx: GraderContext) -> CheckResult:
    if ctx.db_dsn is None:
        return CheckResult(False, "DB DSN unavailable (set DB_HOST etc.)")
    sql = params.get("sql")
    if not sql:
        return CheckResult(False, "sql field missing")
    try:
        import psycopg
    except ImportError:
        return CheckResult(False, "psycopg not installed")
    try:
        with psycopg.connect(ctx.db_dsn) as conn, conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
    except Exception as exc:
        return CheckResult(False, f"SQL error: {exc}")
    if row is None:
        return CheckResult(False, "no rows returned")
    actual = row[0]
    op = params.get("op", "eq")
    expected = params.get("expected")
    ok = _compare(actual, op, expected)
    msg = f"actual={actual!r} {op} expected={expected!r}"
    return CheckResult(ok, msg)


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "gte":
        return actual >= expected
    if op == "gt":
        return actual > expected
    if op == "lte":
        return actual <= expected
    if op == "lt":
        return actual < expected
    if op == "in":
        return actual in expected
    if op == "between":
        lo, hi = expected
        return lo <= actual <= hi
    raise ValueError(f"unsupported op: {op}")


# ---------------------------------------------------------------------------
# file_exists
# ---------------------------------------------------------------------------

def run_file_exists(params: dict, ctx: GraderContext) -> CheckResult:
    path = params.get("path")
    if not path:
        return CheckResult(False, "path field missing")
    full = (ctx.repo_root / path).resolve()
    if not full.exists():
        return CheckResult(False, f"file missing: {path}")
    return CheckResult(True, f"file exists: {path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tail(s: str, n: int = 15) -> str:
    return "\n".join(s.splitlines()[-n:])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

CheckFn = Callable[[dict, GraderContext], CheckResult]

CHECK_TYPES: Dict[str, CheckFn] = {
    "dbt_command": run_dbt_command,
    "manifest_node_exists": run_manifest_node_exists,
    "manifest_lineage": run_manifest_lineage,
    "manifest_config": run_manifest_config,
    "dbt_test_passes": run_dbt_test_passes,
    "sql_assert": run_sql_assert,
    "file_exists": run_file_exists,
}
