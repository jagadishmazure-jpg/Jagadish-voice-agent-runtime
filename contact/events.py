"""Streaming conversation context for analytics.

Every transcript turn, sentiment score, intent change and handoff is
published as a schema-checked event to a sink: an in-process queue (stands
in for a message broker) or an append-only JSON-lines file. Payload text is
masked before it reaches any sink; the schema rejects unknown event types,
missing fields and extra keys.
"""
from __future__ import annotations

import json
import math
import pathlib
import queue
from dataclasses import dataclass, field
from typing import Any

from .pii import mask_obj

SCHEMA_VERSION = 1
EVENT_SCHEMA: dict[str, dict[str, type | tuple[type, ...]]] = {
    "transcript": {"speaker": str, "text": str, "confidence": (int, float)},
    "sentiment": {"score": (int, float)},
    "intent": {"intent": str},
    "handoff": {"reason": str, "to": str},
}
ENVELOPE = ("schema_version", "event_type", "call_id", "seq", "ts_ms", "payload")


class SchemaError(ValueError):
    pass


def validate(event: dict[str, Any]) -> None:
    if set(event) != set(ENVELOPE):
        raise SchemaError(f"envelope keys must be exactly {ENVELOPE}")
    if event["schema_version"] != SCHEMA_VERSION:
        raise SchemaError("unsupported schema_version")
    spec = EVENT_SCHEMA.get(event["event_type"])
    if spec is None:
        raise SchemaError(f"unknown event_type {event['event_type']!r}")
    if not isinstance(event["seq"], int) or not isinstance(event["ts_ms"], int):
        raise SchemaError("seq and ts_ms must be integers")
    payload = event["payload"]
    if set(payload) != set(spec):
        raise SchemaError(f"payload keys must be exactly {sorted(spec)}")
    for k, t in spec.items():
        v = payload[k]
        if isinstance(v, bool) or not isinstance(v, t):
            raise SchemaError(f"payload.{k} has the wrong type")
        if isinstance(v, float) and not math.isfinite(v):
            raise SchemaError(f"payload.{k} must be finite")


class QueueSink:
    def __init__(self) -> None:
        self.q: queue.Queue[dict[str, Any]] = queue.Queue()

    def write(self, event: dict[str, Any]) -> None:
        self.q.put(event)

    def drain(self) -> list[dict[str, Any]]:
        out = []
        while not self.q.empty():
            out.append(self.q.get_nowait())
        return out


class FileSink:
    def __init__(self, path: str | pathlib.Path) -> None:
        self.path = pathlib.Path(path)

    def write(self, event: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")

    def read(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]


@dataclass
class Publisher:
    call_id: str
    sinks: list[Any]
    seq: int = 0
    rejected: int = field(default=0)

    def publish(self, event_type: str, payload: dict[str, Any], ts_ms: int) -> dict[str, Any]:
        event = {"schema_version": SCHEMA_VERSION, "event_type": event_type, "call_id": self.call_id,
                 "seq": self.seq, "ts_ms": ts_ms, "payload": mask_obj(payload)}
        try:
            validate(event)
        except SchemaError:
            self.rejected += 1
            raise
        self.seq += 1
        for s in self.sinks:
            s.write(event)
        return event
