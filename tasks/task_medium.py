"""
AgentCare X — Task 2 (Medium): Angry Customer Refund

Customer is upset about a delayed order (high emotion). Agent must
de-escalate, check the order, and process a refund.
"""

TASK: dict = {
    "task_id": "medium",
    "difficulty": "medium",
    "description": (
        "An angry customer has been waiting for a delayed order and wants a refund. "
        "The agent must empathize with the customer, look up the order status, "
        "and process the refund. The customer's emotion must decrease."
    ),
    "initial_emotion": 0.7,
    "max_steps": 10,
    "required_tools": ["check_order_status", "process_refund"],
    "expected_steps": 5,
    "success_conditions": [
        "tool:check_order_status called",
        "tool:process_refund called",
        "emotion_reduced",
    ],
    "order_data": {
        "order_id": "ORD-20240310-042",
        "product": "Smart Fitness Watch",
        "status": "delayed",
        "amount": 149.99,
        "order_date": "2024-03-10",
        "estimated_delivery": "2024-03-17",
    },
    "id": "medium",
    "prompt": "Where is my delayed order?",
    "expected_output": "I will check your order and process a refund.",
}
from .utils import keyword_grader
TASK["grader"] = keyword_grader
