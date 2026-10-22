# Security Policy

## Scope

This is a deterministic, offline simulation of a voice-agent runtime. It ships
with fake speech-to-text and text-to-speech adapters and a rule-based demo
agent. It processes no real audio, stores no real customer data, and makes no
network calls.

## Security controls demonstrated

- **Confirmation gate for side effects.** Actions that change state (order
  cancellation in the demo agent) never execute on the first request. The
  runtime requires an explicit spoken "yes" in a separate confirmation turn;
  "no" or repeated ambiguity rejects the action.
- **Low-confidence handling.** When speech recognition confidence is low, the
  runtime clarifies or hands off to a human instead of guessing — including
  on confirmation turns.
- **Least privilege by design.** The pluggable responder only receives the
  final transcript and session context the runtime chooses to pass; adapters
  are interfaces, so real STT/TTS services can be scoped and credentialed
  outside this codebase.
- **No secrets in the repo.** There are no API keys, tokens, or credentials.
  Real deployments must inject provider credentials via environment/secret
  management, never in code.

## Reporting a vulnerability

This is a portfolio/demo project. If you spot a security issue in the code,
open a GitHub issue describing the problem and the affected file. Do not
include real personal data in the report.
