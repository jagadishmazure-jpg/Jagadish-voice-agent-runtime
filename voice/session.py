"""Session runner: scripted calls in, call reports out."""
from __future__ import annotations

from .agent import SupportAgent
from .pipeline import CallReport, VoicePipeline


def run_scenario(scenario) -> CallReport:
    """Run one scripted scenario on a fresh pipeline and agent."""
    pipeline = VoicePipeline(agent=SupportAgent())
    return pipeline.run_call(scenario.turns, scenario=scenario.name)


def run_suite(scenarios) -> list[CallReport]:
    return [run_scenario(s) for s in scenarios]
