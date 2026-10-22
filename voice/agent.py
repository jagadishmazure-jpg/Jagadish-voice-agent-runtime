"""A deterministic rule-based support agent for a fictional retailer.

The responder is deliberately pluggable: the runtime only needs an object
with ``respond(text) -> AgentReply`` and ``execute(action)``. This demo
agent answers for "Cinder Peak Outfitters", a fictional outdoor retailer.
All data is invented; order IDs look like ``CP-1001``.

Side-effecting requests (cancel an order) never execute inside ``respond``:
they come back as a ``PendingAction`` and only run through ``execute`` after
the runtime's confirmation gate has collected an explicit spoken "yes".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ORDER_RE = re.compile(r"CP-\d{4}")

ORDERS: dict[str, dict[str, str]] = {
    "CP-1001": {"item": "insulated trail jacket", "status": "shipped", "eta": "Thursday"},
    "CP-1002": {"item": "merino hiking socks", "status": "out for delivery", "eta": "today"},
    "CP-1003": {"item": "three-season tent", "status": "processing", "eta": "next week"},
}

POLICY_SHORT = (
    "You can return any item within sixty days for a full refund, "
    "as long as it is unused."
)
POLICY_DETAILED = (
    "Our full returns policy gives you sixty days from delivery to return any "
    "item for a complete refund, provided the item is unused and in its "
    "original packaging. Refunds land on your original payment method within "
    "five business days of the return reaching our warehouse. Items marked "
    "final sale, gift cards, and worn footwear cannot be returned. If an item "
    "arrives damaged, contact us within fourteen days and we will arrange a "
    "free return label and a replacement or full refund, whichever you prefer."
)


@dataclass
class PendingAction:
    kind: str  # e.g. "cancel_order"
    order_id: str
    description: str


@dataclass
class AgentReply:
    text: str
    pending_action: PendingAction | None = None
    fact: str | None = None  # outcome fact recorded when the reply is heard


class SupportAgent:
    def __init__(self) -> None:
        self.cancelled: set[str] = set()
        self.last_order_id: str | None = None

    # -- helpers ---------------------------------------------------------
    def _order_id(self, text: str) -> str | None:
        match = ORDER_RE.search(text.upper())
        return match.group(0) if match else None

    def _status_text(self, order_id: str) -> str:
        if order_id in self.cancelled:
            return f"Order {order_id} has been cancelled, so it is no longer on its way."
        order = ORDERS.get(order_id)
        if order is None:
            return f"I could not find order {order_id}. Could you check the number and try again?"
        return (
            f"Order {order_id} for the {order['item']} is {order['status']} "
            f"and should arrive {order['eta']}."
        )

    # -- main entry points ------------------------------------------------
    def respond(self, text: str) -> AgentReply:
        lowered = text.lower()
        order_id = self._order_id(text)
        if order_id:
            self.last_order_id = order_id

        if any(p in lowered for p in ("real person", "human", "representative", "speak to someone")):
            return AgentReply(
                text="Of course. I will connect you to a human specialist now.",
                fact="handoff",
            )

        if "cancel" in lowered and order_id:
            if order_id in self.cancelled:
                return AgentReply(text=f"Order {order_id} is already cancelled.")
            order = ORDERS.get(order_id)
            item = order["item"] if order else "item"
            action = PendingAction(
                kind="cancel_order",
                order_id=order_id,
                description=f"cancel order {order_id} ({item})",
            )
            return AgentReply(
                text=f"I can cancel order {order_id} for the {item}. Shall I go ahead?",
                pending_action=action,
            )

        if "return" in lowered or "refund policy" in lowered:
            detailed = any(w in lowered for w in ("detail", "full", "exactly", "explain"))
            return AgentReply(
                text=POLICY_DETAILED if detailed else POLICY_SHORT,
                fact="policy_delivered",
            )

        if order_id and any(w in lowered for w in ("where", "status", "track", "arrive", "delivery", "order")):
            return AgentReply(text=self._status_text(order_id), fact="status_delivered")

        if order_id:
            # A bare order reference (e.g. a self-correction: "I meant CP-1002")
            # is treated as a status request for that order.
            return AgentReply(text=self._status_text(order_id), fact="status_delivered")

        if ("arrive" in lowered or "when" in lowered) and self.last_order_id:
            order = ORDERS[self.last_order_id]
            return AgentReply(
                text=f"It should arrive {order['eta']} by 8 PM.",
                fact="status_delivered",
            )

        if any(w in lowered for w in ("hello", "hi there", "hey")) or lowered.strip() in ("hi", "hello"):
            return AgentReply(text="Hello, this is Cinder Peak Outfitters support. How can I help?")

        return AgentReply(
            text=(
                "I can help with order status, cancellations, and returns. "
                "What would you like to do?"
            )
        )

    def execute(self, action: PendingAction) -> str:
        if action.kind == "cancel_order":
            self.cancelled.add(action.order_id)
            return (
                f"Done. Order {action.order_id} has been cancelled, "
                "and a confirmation is on its way to you."
            )
        return "Done."
