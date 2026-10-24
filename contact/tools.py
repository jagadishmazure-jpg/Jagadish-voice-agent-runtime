"""Mock MCP-style tools the AI agent can call during a live call.

Each tool publishes a descriptor (name, description, JSON-Schema input) the
way an MCP server lists tools, and every call is validated against that
schema: unknown tools, missing fields, extra keys and wrong types are
refused. Side-effecting tools (reschedule) also require a consent token that
only the runtime's confirmation gate can mint; the model cannot set it.
All data is fictional.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any

ORDERS: dict[str, dict[str, str]] = {
    "CP-1001": {"item": "insulated trail jacket", "status": "shipped", "delivery": "2026-11-05", "owner": "C-100"},
    "CP-1002": {"item": "merino hiking socks", "status": "out for delivery", "delivery": "2026-11-02", "owner": "C-101"},
    "CP-1003": {"item": "three-season tent", "status": "processing", "delivery": "2026-11-09", "owner": "C-102"},
    "CP-1004": {"item": "camp stove", "status": "processing", "delivery": "2026-11-07", "owner": "C-103"},
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TYPES = {"string": str, "boolean": bool, "integer": int}


class ToolError(ValueError):
    pass


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    side_effect: bool = False


@dataclass
class ToolServer:
    """In-process stand-in for an MCP server exposing order tools."""

    orders: dict[str, dict[str, str]] = field(default_factory=lambda: {k: dict(v) for k, v in ORDERS.items()})
    calls: list[dict[str, Any]] = field(default_factory=list)
    _consent: set[str] = field(default_factory=set)

    SPECS = (
        ToolSpec("lookup_order", "Read status and delivery date of one order.",
                 {"type": "object", "properties": {"order_id": {"type": "string"}},
                  "required": ["order_id"], "additionalProperties": False}),
        ToolSpec("reschedule_delivery", "Move an order's delivery date. Needs caller consent.",
                 {"type": "object", "properties": {"order_id": {"type": "string"}, "new_date": {"type": "string"},
                                                   "consent_token": {"type": "string"}},
                  "required": ["order_id", "new_date", "consent_token"], "additionalProperties": False},
                 side_effect=True),
    )

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "description": s.description, "inputSchema": s.input_schema} for s in self.SPECS]

    def mint_consent(self) -> str:
        """Called only by the confirmation gate after an explicit spoken yes."""
        token = secrets.token_hex(8)
        self._consent.add(token)
        return token

    def _validate(self, spec: ToolSpec, args: dict[str, Any]) -> None:
        schema = spec.input_schema
        extra = set(args) - set(schema["properties"])
        if extra:
            raise ToolError(f"unexpected arguments: {sorted(extra)}")
        missing = [k for k in schema["required"] if k not in args]
        if missing:
            raise ToolError(f"missing arguments: {missing}")
        for k, v in args.items():
            if not isinstance(v, _TYPES[schema["properties"][k]["type"]]):
                raise ToolError(f"argument {k} has the wrong type")

    def call_tool(self, name: str, args: dict[str, Any], actor: str = "ai") -> dict[str, Any]:
        spec = next((s for s in self.SPECS if s.name == name), None)
        if spec is None:
            raise ToolError(f"unknown tool: {name}")
        self._validate(spec, args)
        order = self.orders.get(args["order_id"])
        if order is None:
            raise ToolError("order not found")
        if name == "lookup_order":
            result = {"order_id": args["order_id"], "item": order["item"], "status": order["status"],
                      "delivery": order["delivery"]}
        else:
            if args["consent_token"] not in self._consent:
                raise ToolError("no valid consent for a side-effecting tool")
            self._consent.discard(args["consent_token"])  # single use
            if not DATE_RE.match(args["new_date"]):
                raise ToolError("new_date must be YYYY-MM-DD")
            if order["status"] not in ("processing", "shipped"):
                raise ToolError(f"cannot reschedule an order that is {order['status']}")
            old = order["delivery"]
            order["delivery"] = args["new_date"]
            result = {"order_id": args["order_id"], "old_date": old, "new_date": args["new_date"]}
        self.calls.append({"tool": name, "actor": actor, "order_id": args["order_id"]})
        return result
