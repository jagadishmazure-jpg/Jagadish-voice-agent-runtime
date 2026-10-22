"""Run the scripted scenario suite and print the call report summary.

Usage: python demos/demo_run.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.metrics import suite_summary  # noqa: E402
from evaluation.scenarios import SCENARIOS  # noqa: E402


def main() -> None:
    summary = suite_summary()
    print("Voice agent runtime - scripted scenario suite")
    print("=" * 60)
    for scenario, report in zip(SCENARIOS, summary["reports"]):
        breaches = report.breaches()
        breach_txt = (
            ", ".join(f"{b.stage} {b.actual_ms}ms>{b.budget_ms}ms" for b in breaches)
            if breaches
            else "none"
        )
        outcome = "PASS" if scenario.expected_fact in report.facts else "FAIL"
        print(f"[{outcome}] {scenario.name}: {len(report.turns)} turns, breaches: {breach_txt}")
    print("-" * 60)
    print(f"task completion:          {summary['task_completion']} ({summary['task_completion_rate']:.0%})")
    print(f"time-to-first-audio p95:  {summary['ttfa_p95_ms']} ms (budget {summary['ttfa_budget_ms']} ms)")
    print(f"interruption success:     {summary['interruption_success']} ({summary['interruption_rate']:.0%})")
    print(f"fallback appropriateness: {summary['fallback_appropriateness']} ({summary['fallback_rate']:.0%})")
    print(f"total budget breaches:    {summary['total_budget_breaches']}")


if __name__ == "__main__":
    main()
