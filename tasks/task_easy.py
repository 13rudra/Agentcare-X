"""
AgentCare X — Task 1 (Easy): Order Lookup FAQ

Customer asks about their order status. Agent must use check_order_status
and relay the information. Simple, single-tool resolution.
"""

TASK: dict = {
    "task_id": "easy",
    "difficulty": "easy",
    "description": (
        "A calm customer wants to know the status of their order. "
        "The agent should look up the order using check_order_status "
        "and provide the delivery information."
    ),
    "initial_emotion": 0.2,
    "max_steps": 10,
    "required_tools": ["check_order_status"],
    "expected_steps": 3,
    "success_conditions": [
        "tool:check_order_status called",
    ],
    "order_data": {
        "order_id": "ORD-20240315-001",
        "product": "Wireless Bluetooth Headphones",
        "status": "shipped",
        "amount": 79.99,
        "order_date": "2024-03-15",
        "estimated_delivery": "2024-03-22",
    },
}
