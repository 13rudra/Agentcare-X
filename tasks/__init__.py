"""AgentCare X — Task definitions package."""
from .task_easy import TASK as TASK_EASY
from .task_medium import TASK as TASK_MEDIUM
from .task_hard import TASK as TASK_HARD
from .task_out_of_stock import TASK as TASK_OUT_OF_STOCK
from .task_subscription import TASK as TASK_SUBSCRIPTION

TASKS = [
    TASK_EASY,
    TASK_MEDIUM,
    TASK_HARD,
    TASK_OUT_OF_STOCK,
    TASK_SUBSCRIPTION
]
