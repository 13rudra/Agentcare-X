"""
AgentCare X — Tool Registry

Deterministic tool implementations for the customer support environment.
Each tool takes validated parameters and returns a structured dict result.
"""

from __future__ import annotations

from typing import Any

from models import OrderInfo, ToolSpec




# ---------------------------------------------------------------------------
# Tool specifications (shown to agents in Observation.available_tools)
# ---------------------------------------------------------------------------

TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="check_order_status",
        description="Look up current status, tracking, and delivery estimate for an order.",
        parameters={"order_id": "string — the order ID to look up"},
    ),
    ToolSpec(
        name="process_refund",
        description="Initiate a refund for a given order. Requires a reason.",
        parameters={
            "order_id": "string — the order ID to refund",
            "reason": "string — reason for the refund (e.g. 'delayed', 'wrong_item')",
        },
    ),
    ToolSpec(
        name="escalate_to_manager",
        description="Escalate the case to a human manager for further review.",
        parameters={
            "order_id": "string — the order ID",
            "reason": "string — why the case needs escalation",
        },
    ),
    # NEW — Out of Stock tools
    ToolSpec(
        name="check_inventory",
        description="Check current inventory and restock ETA for a product.",
        parameters={"product_name": "string — the product name to check"},
    ),
    # NEW — Subscription Management tools
    ToolSpec(
        name="check_subscription",
        description="Look up subscription details, billing cycle, and current plan.",
        parameters={"order_id": "string — the subscription / order ID"},
    ),
    ToolSpec(
        name="apply_retention_discount",
        description="Apply a retention discount to keep the customer subscribed.",
        parameters={
            "order_id": "string — the subscription / order ID",
            "discount_percent": "integer — discount percentage to apply (e.g. 20)",
        },
    ),
]

VALID_TOOL_NAMES = {spec.name for spec in TOOL_SPECS}


# ---------------------------------------------------------------------------
# Tool execution engine
# ---------------------------------------------------------------------------

def execute_tool(
    tool_name: str,
    parameters: dict[str, Any] | None,
    order: OrderInfo,
    *,
    refund_processed: bool = False,
    escalation_done: bool = False,
) -> dict[str, Any]:
    """
    Execute a tool deterministically and return a result dict.

    Returns {"error": "...", "hallucinated": True} for unknown tool names.
    Returns {"error": "..."} for bad parameters.
    """
    # NEW — hallucinated tool detection
    if tool_name not in VALID_TOOL_NAMES:
        return {
            "error": f"Unknown tool '{tool_name}'. Available: {sorted(VALID_TOOL_NAMES)}",
            "hallucinated": True,
        }

    params = parameters or {}

    if tool_name == "check_order_status":
        return _check_order_status(params, order)
    elif tool_name == "process_refund":
        return _process_refund(params, order, refund_processed)
    elif tool_name == "escalate_to_manager":
        return _escalate_to_manager(params, order, escalation_done)
    elif tool_name == "check_inventory":
        return _check_inventory(params, order)
    elif tool_name == "check_subscription":
        return _check_subscription(params, order)
    elif tool_name == "apply_retention_discount":
        return _apply_retention_discount(params, order)

    return {"error": "Unexpected tool dispatch failure."}


# ---------------------------------------------------------------------------
# Individual tool implementations
# ---------------------------------------------------------------------------

def _check_order_status(params: dict, order: OrderInfo) -> dict[str, Any]:
    oid = params.get("order_id", "")
    if oid != order.order_id:
        return {"error": f"Order '{oid}' not found. Valid order: {order.order_id}"}
    return {
        "success": True,
        "order_id": order.order_id,
        "product": order.product,
        "status": order.status,
        "amount": order.amount,
        "order_date": order.order_date,
        "estimated_delivery": order.estimated_delivery,
    }


def _process_refund(params: dict, order: OrderInfo, already_processed: bool) -> dict[str, Any]:
    oid = params.get("order_id", "")
    reason = params.get("reason", "")

    if oid != order.order_id:
        return {"error": f"Order '{oid}' not found. Valid order: {order.order_id}"}
    if not reason:
        return {"error": "Parameter 'reason' is required for process_refund."}
    if already_processed:
        return {"error": "Refund has already been processed for this order."}
    if order.status not in ("wrong_item", "delayed", "out_of_stock"):
        return {"error": f"Refund not applicable for order status '{order.status}'."}

    return {
        "success": True,
        "message": f"Refund of ${order.amount:.2f} initiated for order {order.order_id}. Reason: {reason}.",
        "refund_amount": order.amount,
    }


def _escalate_to_manager(params: dict, order: OrderInfo, already_escalated: bool) -> dict[str, Any]:
    oid = params.get("order_id", "")
    reason = params.get("reason", "")

    if oid != order.order_id:
        return {"error": f"Order '{oid}' not found. Valid order: {order.order_id}"}
    if not reason:
        return {"error": "Parameter 'reason' is required for escalate_to_manager."}
    if already_escalated:
        return {"error": "Case has already been escalated."}

    return {
        "success": True,
        "message": f"Case escalated to manager for order {order.order_id}.",
        "ticket_id": f"ESC-{order.order_id}-001",
    }


# NEW — Out of Stock tool
def _check_inventory(params: dict, order: OrderInfo) -> dict[str, Any]:
    product_name = params.get("product_name", "")
    if not product_name:
        return {"error": "Parameter 'product_name' is required for check_inventory."}

    # Deterministic inventory simulation
    if order.status == "out_of_stock":
        return {
            "success": True,
            "product": order.product,
            "in_stock": False,
            "restock_eta": "2024-04-15",
            "alternatives": [
                {"name": f"{order.product} — Refurbished", "price": round(order.amount * 0.8, 2)},
                {"name": f"{order.product} — Next Gen", "price": round(order.amount * 1.1, 2)},
            ],
            "message": f"{order.product} is currently out of stock. Restock ETA: April 15, 2024. 2 alternatives available.",
        }
    return {
        "success": True,
        "product": order.product,
        "in_stock": True,
        "quantity": 42,
        "message": f"{order.product} is in stock.",
    }


# NEW — Subscription Management tools
def _check_subscription(params: dict, order: OrderInfo) -> dict[str, Any]:
    oid = params.get("order_id", "")
    if oid != order.order_id:
        return {"error": f"Subscription '{oid}' not found. Valid ID: {order.order_id}"}

    return {
        "success": True,
        "subscription_id": order.order_id,
        "plan": order.product,
        "status": "active",
        "monthly_amount": order.amount,
        "billing_cycle_start": order.order_date,
        "billing_cycle_end": order.estimated_delivery,
        "days_remaining": 18,
        "proration_refund": round(order.amount * 18 / 30, 2),
        "message": (
            f"Subscription to {order.product} is active at ${order.amount:.2f}/month. "
            f"18 days remain in current cycle. Proration refund would be ${order.amount * 18 / 30:.2f}."
        ),
    }


def _apply_retention_discount(params: dict, order: OrderInfo) -> dict[str, Any]:
    oid = params.get("order_id", "")
    discount = params.get("discount_percent", 0)

    if oid != order.order_id:
        return {"error": f"Subscription '{oid}' not found. Valid ID: {order.order_id}"}
    if not discount or not isinstance(discount, (int, float)) or discount <= 0:
        return {"error": "Parameter 'discount_percent' must be a positive number."}
    if discount > 50:
        return {"error": "Maximum retention discount is 50%."}

    new_price = round(order.amount * (1 - discount / 100), 2)
    return {
        "success": True,
        "message": (
            f"Retention discount of {discount}% applied to {order.product}. "
            f"New monthly price: ${new_price} (was ${order.amount:.2f})."
        ),
        "new_monthly_amount": new_price,
        "discount_applied": discount,
    }
