"""Markdown / stdout report generator for the grader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class CheckOutcome:
    id: str
    description: str
    passed: bool
    points_earned: int
    points_max: int
    message: str
    details: str = ""


@dataclass
class GradingResult:
    exercise: str
    title: str
    passing_score: int
    outcomes: List[CheckOutcome]

    @property
    def total_earned(self) -> int:
        return sum(o.points_earned for o in self.outcomes)

    @property
    def total_max(self) -> int:
        return sum(o.points_max for o in self.outcomes)

    @property
    def percentage(self) -> int:
        if self.total_max == 0:
            return 0
        return int(round(self.total_earned * 100 / self.total_max))

    @property
    def overall_passed(self) -> bool:
        return self.percentage >= self.passing_score


def to_stdout(result: GradingResult) -> str:
    lines = [
        "",
        f"Exercise {result.exercise}: {result.title}",
        "=" * 60,
    ]
    for o in result.outcomes:
        mark = "[OK]" if o.passed else "[NG]"
        lines.append(
            f"  {mark} {o.id:<30} {o.points_earned:>3}/{o.points_max:<3}  {o.message}"
        )
        if o.details:
            for line in o.details.splitlines():
                lines.append(f"        {line}")
    lines.append("-" * 60)
    verdict = "PASS" if result.overall_passed else "FAIL"
    lines.append(
        f"  Total: {result.total_earned}/{result.total_max} "
        f"({result.percentage}%)  passing>={result.passing_score}%  RESULT: {verdict}"
    )
    lines.append("")
    return "\n".join(lines)


def to_markdown(result: GradingResult) -> str:
    verdict = "PASS" if result.overall_passed else "FAIL"
    badge = "OK" if result.overall_passed else "NG"
    out = [
        f"## Grading Result: {badge} ({result.percentage}%)",
        "",
        f"**Exercise**: {result.exercise} — {result.title}",
        f"**Score**: {result.total_earned} / {result.total_max} (passing >= {result.passing_score}%)",
        f"**Verdict**: **{verdict}**",
        "",
        "| | Check | Score | Note |",
        "|---|---|---|---|",
    ]
    for o in result.outcomes:
        mark = "OK" if o.passed else "NG"
        msg = o.message.replace("|", r"\|")
        out.append(f"| {mark} | `{o.id}` — {o.description} | {o.points_earned}/{o.points_max} | {msg} |")
    out.append("")
    if any(o.details for o in result.outcomes):
        out.append("<details><summary>Failure details</summary>")
        out.append("")
        for o in result.outcomes:
            if not o.passed and o.details:
                out.append(f"### {o.id}")
                out.append("```")
                out.append(o.details)
                out.append("```")
        out.append("</details>")
    return "\n".join(out)
