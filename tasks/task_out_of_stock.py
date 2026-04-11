"""
AgentCare X — Task 4 (Medium): Out of Stock

Customer ordered a product that turns out to be out of stock.
Agent must check inventory, offer alternatives or restock ETA,
and apply a discount if the customer agrees to wait.
"""

TASK: dict = {
    "task_id": "out_of_stock",
    "difficulty": "medium",
    "description": (
        "A frustrated customer ordered a product that is now out of stock. "
        "The agent must: (1) check the order to confirm the issue, "
        "(2) check inventory for restock ETA and alternatives, "
        "(3) offer alternatives or a discount for waiting, "
        "and (4) de-escalate the customer's emotions."
    ),
    "initial_emotion": 0.6,
    "max_steps": 10,
    "required_tools": ["check_order_status", "check_inventory"],
    "expected_steps": 5,
    "success_conditions": [
        "tool:check_order_status called",
        "tool:check_inventory called",
        "emotion_reduced",
    ],
    "grading_weights": {
        "resolution": 0.40,
        "tool_usage": 0.30,
        "emotional_iq": 0.30,
    },
    "order_data": {
        "order_id": "ORD-20240320-088",
        "product": "4K Mirrorless Camera",
        "status": "out_of_stock",
        "amount": 899.99,
        "order_date": "2024-03-20",
        "estimated_delivery": "2024-03-28",
    },

    "id": "out_of_stock",
    "prompt": "My camera is out of stock.",
    "expected_output": "I can check inventory and offer alternatives."
}
from .utils import keyword_grader
TASK["grader"] = keyword_grader
