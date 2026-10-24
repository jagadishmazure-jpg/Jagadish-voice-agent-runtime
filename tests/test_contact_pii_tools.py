import logging

import pytest

from contact.pii import MaskingFormatter, has_pii, luhn_ok, mask, mask_obj
from contact.tools import ToolError, ToolServer


@pytest.mark.parametrize("raw", ["4111 1111 1111 1111", "4111-1111-1111-1111", "5500005555555559", "378282246310005"])
def test_cards_masked(raw):
    assert mask(f"card {raw} ok") == "card [CARD] ok"


def test_non_luhn_digits_and_order_ids_untouched():
    assert mask("ref 1234 5678 9012 3456") == "ref 1234 5678 9012 3456"
    assert mask("order CP-1001") == "order CP-1001"
    assert not luhn_ok("1234567890123456")


@pytest.mark.parametrize("raw", ["415-555-0142", "(415) 555-0142", "+1 415 555 0142", "415.555.0142"])
def test_phones_masked(raw):
    assert "[PHONE]" in mask(f"call {raw}") and "0142" not in mask(f"call {raw}")


def test_email_and_ssn_masked():
    out = mask("mail ana.lindqvist@example.com ssn 123-45-6789")
    assert out == "mail [EMAIL] ssn [SSN]"


def test_dates_and_times_not_masked():
    assert mask("move to 2026-11-14 at 10:30") == "move to 2026-11-14 at 10:30"


def test_mask_obj_nested():
    out = mask_obj({"a": ["x@y.io", ("123-45-6789",)], "n": 3})
    assert out == {"a": ["[EMAIL]", ("[SSN]",)], "n": 3}


def test_log_formatter_masks(caplog):
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "caller %s said card %s", ("a@b.co", "4111111111111111"),
                            None)
    line = MaskingFormatter("%(message)s").format(rec)
    assert not has_pii(line) and "[EMAIL]" in line and "[CARD]" in line


def test_tool_listing_is_mcp_shaped():
    tools = ToolServer().list_tools()
    assert {t["name"] for t in tools} == {"lookup_order", "reschedule_delivery"}
    assert all("inputSchema" in t and t["inputSchema"]["additionalProperties"] is False for t in tools)


def test_lookup_order():
    assert ToolServer().call_tool("lookup_order", {"order_id": "CP-1001"})["status"] == "shipped"


@pytest.mark.parametrize("name,args", [
    ("delete_order", {"order_id": "CP-1001"}),
    ("lookup_order", {}),
    ("lookup_order", {"order_id": "CP-1001", "admin": True}),
    ("lookup_order", {"order_id": 1001}),
    ("lookup_order", {"order_id": "CP-9999"}),
])
def test_tool_input_rejected(name, args):
    with pytest.raises(ToolError):
        ToolServer().call_tool(name, args)


def test_reschedule_needs_minted_single_use_consent():
    s = ToolServer()
    with pytest.raises(ToolError, match="consent"):
        s.call_tool("reschedule_delivery", {"order_id": "CP-1003", "new_date": "2026-11-12", "consent_token": "x"})
    tok = s.mint_consent()
    assert s.call_tool("reschedule_delivery", {"order_id": "CP-1003", "new_date": "2026-11-12",
                                               "consent_token": tok})["new_date"] == "2026-11-12"
    with pytest.raises(ToolError, match="consent"):
        s.call_tool("reschedule_delivery", {"order_id": "CP-1003", "new_date": "2026-11-13", "consent_token": tok})


def test_reschedule_refuses_out_for_delivery_and_bad_date():
    s = ToolServer()
    with pytest.raises(ToolError, match="out for delivery"):
        s.call_tool("reschedule_delivery", {"order_id": "CP-1002", "new_date": "2026-11-12",
                                            "consent_token": s.mint_consent()})
    with pytest.raises(ToolError, match="YYYY"):
        s.call_tool("reschedule_delivery", {"order_id": "CP-1001", "new_date": "next tuesday",
                                            "consent_token": s.mint_consent()})
    assert s.orders["CP-1001"]["delivery"] == "2026-11-05"
