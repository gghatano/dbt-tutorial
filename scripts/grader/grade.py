"""dbt-tutorial 採点ランナー.

Reads docs/exercises/<exercise>.grading.yaml, runs each check against the
learner's dbt project + Postgres, and emits a stdout summary, a markdown
report (for PR comments), and an exit code.

Usage
-----
    python scripts/grader/grade.py --exercise 06
    python scripts/grader/grade.py --exercise 06 --report build/report.md
    python scripts/grader/grade.py --grading-file docs/exercises/06-exposures-and-docs.grading.yaml

Exit codes
----------
    0  passing_score met
    1  failing
    2  setup error (missing files, bad YAML, etc.)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# allow running as a script or as a module
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from checks import CHECK_TYPES, GraderContext  # noqa: E402
    from report import CheckOutcome, GradingResult, to_markdown, to_stdout  # noqa: E402
else:
    from .checks import CHECK_TYPES, GraderContext
    from .report import CheckOutcome, GradingResult, to_markdown, to_stdout

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DBT_DIR = REPO_ROOT / "dbt"
DEFAULT_GRADING_DIR = REPO_ROOT / "docs" / "exercises"


def find_grading_file(exercise: str) -> Path:
    """Resolve --exercise to a grading.yaml path.

    Accepts forms: '06', '06-exposures', 'docs/exercises/06-...grading.yaml'.
    """
    p = Path(exercise)
    if p.is_file():
        return p
    candidates = sorted(DEFAULT_GRADING_DIR.glob(f"{exercise}*.grading.yaml"))
    if not candidates:
        # fallback: 100-knock pattern docs/exercises/100-knock/<topic>-<num>-*.grading.yaml
        knock_dir = DEFAULT_GRADING_DIR / "100-knock"
        if knock_dir.exists():
            candidates = sorted(knock_dir.glob(f"{exercise}*.grading.yaml"))
    if not candidates:
        raise FileNotFoundError(f"no grading.yaml matched: {exercise}")
    if len(candidates) > 1:
        names = ", ".join(c.name for c in candidates)
        raise FileNotFoundError(f"multiple grading.yaml matched ({names}); be more specific")
    return candidates[0]


def build_dsn() -> str | None:
    keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    if not all(os.environ.get(k) for k in keys):
        return None
    return (
        f"host={os.environ['DB_HOST']} "
        f"port={os.environ['DB_PORT']} "
        f"dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USER']} "
        f"password={os.environ['DB_PASSWORD']}"
    )


def run(grading_file: Path, dbt_dir: Path) -> GradingResult:
    with grading_file.open() as fh:
        spec = yaml.safe_load(fh)

    exercise = spec.get("exercise") or grading_file.stem.replace(".grading", "")
    title = spec.get("title", exercise)
    passing = int(spec.get("passing_score", 80))
    checks = spec.get("checks") or []

    ctx = GraderContext(
        dbt_dir=dbt_dir,
        repo_root=REPO_ROOT,
        db_dsn=build_dsn(),
        target_path=dbt_dir / "target",
    )

    outcomes: list[CheckOutcome] = []
    for entry in checks:
        cid = entry.get("id", "(unnamed)")
        description = entry.get("description", "")
        ctype = entry.get("type")
        points = int(entry.get("points", 0))
        params = {k: v for k, v in entry.items() if k not in ("id", "description", "type", "points")}
        fn = CHECK_TYPES.get(ctype)
        if fn is None:
            outcomes.append(
                CheckOutcome(
                    id=cid,
                    description=description,
                    passed=False,
                    points_earned=0,
                    points_max=points,
                    message=f"unknown check type: {ctype}",
                )
            )
            continue
        try:
            result = fn(params, ctx)
        except Exception as exc:  # noqa: BLE001 - grader is best-effort
            outcomes.append(
                CheckOutcome(
                    id=cid, description=description, passed=False,
                    points_earned=0, points_max=points,
                    message=f"check raised: {exc}",
                )
            )
            continue
        outcomes.append(
            CheckOutcome(
                id=cid,
                description=description,
                passed=result.passed,
                points_earned=points if result.passed else 0,
                points_max=points,
                message=result.message,
                details=result.details,
            )
        )

    return GradingResult(
        exercise=str(exercise),
        title=title,
        passing_score=passing,
        outcomes=outcomes,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="dbt-tutorial exercise grader")
    parser.add_argument("--exercise", help="exercise id, e.g. '06' or '06-exposures'")
    parser.add_argument("--grading-file", help="explicit path to grading.yaml")
    parser.add_argument("--dbt-dir", default=str(DEFAULT_DBT_DIR), help="dbt project dir")
    parser.add_argument("--report", help="write markdown report to this path")
    parser.add_argument("--quiet", action="store_true", help="suppress stdout summary")
    args = parser.parse_args(argv)

    if not args.exercise and not args.grading_file:
        print("error: --exercise or --grading-file required", file=sys.stderr)
        return 2

    try:
        gf = Path(args.grading_file) if args.grading_file else find_grading_file(args.exercise)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not gf.exists():
        print(f"error: grading file not found: {gf}", file=sys.stderr)
        return 2

    try:
        result = run(gf, Path(args.dbt_dir))
    except Exception as exc:  # noqa: BLE001
        print(f"error: grader failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(to_stdout(result))

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(to_markdown(result))

    return 0 if result.overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
