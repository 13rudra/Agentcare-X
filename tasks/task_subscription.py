"""
AgentCare X — Task 5 (Hard): Subscription Management

Customer wants to downgrade or cancel their subscription mid-billing-cycle.
Agent must check subscription details, explain proration, and attempt retention
with a discount offer before processing cancellation.
"""

TASK: dict = {
    "task_id": "subscription",
    "difficulty": "hard",
    "description": (
        "A frustrated customer wants to cancel their subscription mid-cycle. "
        "The agent must: (1) check the subscription details, "
        "(2) explain the proration / partial refund policy, "
        "(3) offer a retention discount to keep the customer, "
        "and (4) handle the outcome empathetically."
    ),
    "initial_emotion": 0.65,
    "max_steps": 10,
    "required_tools": ["check_subscription", "apply_retention_discount"],
    "expected_steps": 6,
    "success_conditions": [
        "tool:check_subscription called",
        "tool:apply_retention_discount called",
        "emotion_reduced",
    ],
    "grading_weights": {
        "resolution": 0.40,
        "retention_attempt": 0.20,
        "tool_usage": 0.20,
        "emotional_iq": 0.20,
    },
    "order_data": {
        "order_id": "SUB-20240201-005",
        "product": "Premium Cloud Storage Plan",
        "status": "active_subscription",
        "amount": 29.99,
        "order_date": "2024-03-01",
        "estimated_delivery": "2024-03-31",
    },
    "id": "subscription",
    "prompt": "Cancel my subscription.",
    "expected_output": "I can offer a retention discount instead."
}
from .utils import keyword_grader
TASK["grader"] = keyword_grader
