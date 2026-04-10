"""
AgentCare X — Task 3 (Hard): Wrong Item + Refund + Escalation

Customer received a completely wrong item and is furious.
Agent must check the order, process a refund, AND escalate to a manager.
Multi-step resolution chain requiring all three tools.
"""

TASK: dict = {
    "task_id": "hard",
    "difficulty": "hard",
    "description": (
        "A furious customer received the wrong item (ordered a laptop, got headphones). "
        "The agent must: (1) check the order status to confirm the mistake, "
        "(2) process a full refund, (3) escalate the case to a manager, "
        "and (4) de-escalate the customer's emotions throughout. "
        "All three tools must be called successfully."
    ),
    "initial_emotion": 0.85,
    "max_steps": 10,
    "required_tools": ["check_order_status", "process_refund", "escalate_to_manager"],
    "expected_steps": 7,
    "success_conditions": [
        "tool:check_order_status called",
        "tool:process_refund called",
        "tool:escalate_to_manager called",
        "emotion_reduced",
    ],
    "order_data": {
        "order_id": "ORD-20240308-117",
        "product": "15-inch Gaming Laptop",
        "status": "wrong_item",
        "amount": 1299.99,
        "order_date": "2024-03-08",
        "estimated_delivery": "2024-03-15",
    },
}
