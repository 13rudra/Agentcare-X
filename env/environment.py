"""
AgentCare X — Core Environment

Implements the OpenEnv-compliant environment with step(), reset(), and state().
Manages the customer support simulation lifecycle.
"""

from __future__ import annotations

import copy
from typing import Any

from models import (
    AgentAction,
    EnvState,
    Observation,
    OrderInfo,
    RewardInfo,
)
from env.tools import TOOL_SPECS, execute_tool
from env.customer import (
    compute_emotion_delta,
    clamp_emotion,
    get_customer_message,
)
from env.rewards import compute_reward
# NEW — LLM empathy judge
from env.empathy_judge import judge_empathy


# ---------------------------------------------------------------------------
# Task registry (loaded lazily)
# ---------------------------------------------------------------------------

def _load_tasks() -> dict[str, dict[str, Any]]:
    """Import all task definitions."""
    from tasks.task_easy import TASK as easy
    from tasks.task_medium import TASK as medium
    from tasks.task_hard import TASK as hard
    # NEW — additional tasks
    from tasks.task_out_of_stock import TASK as out_of_stock
    from tasks.task_subscription import TASK as subscription
    return {
        easy["task_id"]: easy,
        medium["task_id"]: medium,
        hard["task_id"]: hard,
        out_of_stock["task_id"]: out_of_stock,
        subscription["task_id"]: subscription,
    }


# ---------------------------------------------------------------------------
# System instructions template
# ---------------------------------------------------------------------------

_INSTRUCTIONS_TEMPLATE = """You are a customer support agent. Your goal is to resolve the customer's issue.

AVAILABLE ACTIONS (respond with JSON):
1. Respond to customer:
   {{"action_type": "respond", "message": "Your helpful message here"}}

2. Use a tool:
   {{"action_type": "call_tool", "tool_name": "<tool>", "tool_parameters": {{...}}}}

AVAILABLE TOOLS:
{tools_desc}

CURRENT SITUATION:
- Customer emotion level: {emotion:.1f}/1.0 (higher = more upset)
- Turn {turn}/{max_turns}
- Order: {order_id} — {product} — Status: {status}

GUIDELINES:
- Be empathetic and professional
- Use tools to look up info and take actions
- Acknowledge the customer's feelings before using tools
- Resolve the issue efficiently (fewer steps = better score)
"""


def _format_instructions(
    emotion: float,
    turn: int,
    max_turns: int,
    order: OrderInfo,
) -> str:
    tools_desc = "\n".join(
        f"  - {t.name}: {t.description} | Parameters: {t.parameters}"
        for t in TOOL_SPECS
    )
    return _INSTRUCTIONS_TEMPLATE.format(
        tools_desc=tools_desc,
        emotion=emotion,
        turn=turn,
        max_turns=max_turns,
        order_id=order.order_id,
        product=order.product,
        status=order.status,
    )


# ---------------------------------------------------------------------------
# AgentCareEnv
# ---------------------------------------------------------------------------

class AgentCareEnv:
    """
    OpenEnv-compliant Customer Operations Environment.

    API:
        reset(task_id) → Observation
        step(action)   → (Observation, reward, done, info)
        state()        → EnvState
    """

    def __init__(self, *, use_llm_judge: bool = False) -> None:
        self._tasks: dict[str, dict[str, Any]] = _load_tasks()
        self._state = EnvState()
        self._task: dict[str, Any] = {}
        self._order: OrderInfo = OrderInfo(
            order_id="", product="", status="shipped",
            amount=0, order_date="", estimated_delivery="",
        )
        self._refund_processed: bool = False
        self._escalation_done: bool = False
        self._customer_message_pending: bool = False
        self._consecutive_invalid: int = 0
        self._previous_actions: list[dict] = []
        self._success_flags: dict[str, bool] = {}
        # NEW — LLM judge toggle
        self._use_llm_judge: bool = use_llm_judge

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------

    def reset(self, task_id: str | None = None, **kwargs: Any) -> Observation:
        """Reset environment to a fresh episode for the given task."""
        if task_id is None:
            task_id = "easy"
        if task_id not in self._tasks:
            raise ValueError(f"Unknown task_id '{task_id}'. Available: {list(self._tasks.keys())}")

        self._task = self._tasks[task_id]
        self._order = OrderInfo(**self._task["order_data"])

        initial_emotion: float = self._task["initial_emotion"]
        customer_msg = get_customer_message(task_id, 0, initial_emotion, resolved=False)

        self._state = EnvState(
            task_id=task_id,
            step_count=0,
            max_steps=self._task.get("max_steps", 10),
            resolved=False,
            failed=False,
            failure_reason=None,
            emotion_history=[initial_emotion],
            tool_calls_made=[],
            conversation_history=[{"role": "customer", "content": customer_msg}],
            cumulative_reward=0.0,
            hallucination_count=0,  # NEW
        )
        self._refund_processed = False
        self._escalation_done = False
        self._customer_message_pending = True
        self._consecutive_invalid = 0
        self._previous_actions = []
        self._success_flags = {cond: False for cond in self._task["success_conditions"]}

        return self._build_observation(initial_emotion, customer_msg, feedback=None)

    # ------------------------------------------------------------------
    # step
    # ------------------------------------------------------------------

    def step(self, action: AgentAction) -> tuple[Observation, float, bool, dict[str, Any]]:
        """Execute one agent action and return (observation, reward, done, info)."""
        # --- Validate action schema ---
        validation_error = self._validate_action(action)
        if validation_error:
            self._consecutive_invalid += 1
            # Free retry (don't advance step counter) on first invalid attempt
            if self._consecutive_invalid < 3:
                obs = self._build_observation(
                    self._current_emotion,
                    self._last_customer_message,
                    feedback=f"INVALID ACTION: {validation_error}. Please fix and retry.",
                )
                return obs, -0.05, False, {"error": validation_error, "retry": True}
            else:
                # 3 consecutive invalid → failure
                self._state.failed = True
                self._state.failure_reason = "repeated_invalid_actions"
                obs = self._build_observation(
                    self._current_emotion,
                    self._last_customer_message,
                    feedback="Episode terminated: 3 consecutive invalid actions.",
                )
                return obs, -0.30, True, {"failure": "repeated_invalid_actions"}

        self._consecutive_invalid = 0
        self._state.step_count += 1

        # --- Execute action ---
        tool_result: dict | None = None
        tool_success: bool | None = None
        agent_message: str | None = None
        hallucinated_tool: bool = False  # NEW

        if action.action_type == "respond":
            agent_message = action.message
            self._state.conversation_history.append(
                {"role": "agent", "content": agent_message or ""}
            )
            self._customer_message_pending = False

        elif action.action_type == "call_tool":
            tool_result = execute_tool(
                action.tool_name or "",
                action.tool_parameters,
                self._order,
                refund_processed=self._refund_processed,
                escalation_done=self._escalation_done,
            )
            tool_success = tool_result.get("success", False)

            # NEW — detect hallucinated tool calls
            if tool_result.get("hallucinated"):
                hallucinated_tool = True
                self._state.hallucination_count += 1

            self._state.tool_calls_made.append({
                "tool": action.tool_name,
                "params": action.tool_parameters,
                "result": tool_result,
                "step": self._state.step_count,
                "hallucinated": hallucinated_tool,  # NEW
            })

            # Track state changes from successful tools
            if tool_success and action.tool_name == "process_refund":
                self._refund_processed = True
            if tool_success and action.tool_name == "escalate_to_manager":
                self._escalation_done = True

            # Add tool result to conversation for context
            self._state.conversation_history.append(
                {"role": "agent", "content": f"[Tool: {action.tool_name}] Result: {tool_result}"}
            )

        # --- Update success flags ---
        self._update_success_flags(action, tool_result)

        # --- NEW — get empathy score from LLM judge for emotion delta ---
        empathy_score: float | None = None
        if self._use_llm_judge and agent_message:
            try:
                empathy_score = judge_empathy(agent_message)
            except Exception:
                empathy_score = None  # fallback handled inside compute_emotion_delta

        # --- Compute emotion delta ---
        emotion_delta = compute_emotion_delta(
            agent_message=agent_message,
            action_type=action.action_type,
            tool_success=tool_success,
            current_emotion=self._current_emotion,
            empathy_score=empathy_score,  # NEW
        )
        new_emotion = clamp_emotion(self._current_emotion + emotion_delta)
        self._state.emotion_history.append(new_emotion)

        # --- Check resolution ---
        resolved_this_step = all(self._success_flags.values())
        if resolved_this_step:
            self._state.resolved = True

        # --- Compute reward ---
        tools_already = [tc["tool"] for tc in self._state.tool_calls_made[:-1]] if action.action_type == "call_tool" else [tc["tool"] for tc in self._state.tool_calls_made]
        reward_info = compute_reward(
            action,
            tool_result=tool_result,
            required_tools=self._task["required_tools"],
            tools_already_called=tools_already,
            previous_actions=self._previous_actions,
            step_count=self._state.step_count,
            expected_steps=self._task["expected_steps"],
            max_steps=self._state.max_steps,
            resolved_this_step=resolved_this_step,
            emotion_delta=emotion_delta,
            customer_message_pending=self._customer_message_pending,
            hallucinated_tool=hallucinated_tool,  # NEW
            use_llm_judge=self._use_llm_judge,  # NEW
        )
        self._state.cumulative_reward += reward_info.total

        # --- Record action for dedup ---
        self._previous_actions.append(action.model_dump())

        # --- Check termination ---
        done = False
        info: dict[str, Any] = {"reward_breakdown": reward_info.breakdown}

        if self._state.resolved:
            done = True
            info["result"] = "resolved"

        elif self._state.step_count >= self._state.max_steps:
            done = True
            self._state.failed = True
            self._state.failure_reason = "max_steps_exceeded"
            reward_info.total -= 0.30
            self._state.cumulative_reward -= 0.30
            info["failure"] = "max_steps_exceeded"

        elif new_emotion >= 0.95:
            done = True
            self._state.failed = True
            self._state.failure_reason = "customer_frustration"
            reward_info.total -= 0.40
            self._state.cumulative_reward -= 0.40
            info["failure"] = "customer_frustration"

        # NEW — include hallucination count in info
        info["hallucination_count"] = self._state.hallucination_count

        # --- Generate customer follow-up ---
        customer_msg = self._last_customer_message
        if not done:
            customer_msg = get_customer_message(
                self._state.task_id,
                self._state.step_count,
                new_emotion,
                self._state.resolved,
            )
            self._state.conversation_history.append(
                {"role": "customer", "content": customer_msg}
            )
            self._customer_message_pending = True

        feedback = None
        if tool_result:
            if tool_result.get("hallucinated"):
                feedback = f"HALLUCINATION: Tool '{action.tool_name}' does not exist. -0.20 penalty applied."
            elif tool_result.get("error"):
                feedback = f"Tool error: {tool_result['error']}"
            else:
                feedback = f"Tool '{action.tool_name}' executed successfully: {tool_result.get('message', 'OK')}"

        obs = self._build_observation(new_emotion, customer_msg, feedback=feedback)
        return obs, round(reward_info.total, 4), done, info

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------

    def state(self) -> EnvState:
        """Return a snapshot of the internal environment state."""
        return copy.deepcopy(self._state)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _current_emotion(self) -> float:
        return self._state.emotion_history[-1] if self._state.emotion_history else 0.0

    @property
    def _last_customer_message(self) -> str:
        for msg in reversed(self._state.conversation_history):
            if msg["role"] == "customer":
                return msg["content"]
        return ""

    def _build_observation(
        self, emotion: float, customer_msg: str, feedback: str | None
    ) -> Observation:
        return Observation(
            customer_message=customer_msg,
            emotion_level=emotion,
            order_info=self._order,
            conversation_history=list(self._state.conversation_history),
            available_tools=TOOL_SPECS,
            last_action_feedback=feedback,
            instructions=_format_instructions(
                emotion,
                self._state.step_count,
                self._state.max_steps,
                self._order,
            ),
            turn_number=self._state.step_count,
            max_turns=self._state.max_steps,
        )

    def _validate_action(self, action: AgentAction) -> str | None:
        """Return an error string if the action is invalid, else None."""
        if action.action_type == "respond":
            if not action.message or not action.message.strip():
                return "action_type='respond' requires a non-empty 'message' field."
        elif action.action_type == "call_tool":
            if not action.tool_name:
                return "action_type='call_tool' requires a 'tool_name' field."
            if action.tool_parameters is None:
                return "action_type='call_tool' requires a 'tool_parameters' dict."
        return None

    def _update_success_flags(self, action: AgentAction, tool_result: dict | None) -> None:
        """Check each success condition and mark as met if applicable."""
        for cond in self._success_flags:
            if self._success_flags[cond]:
                continue  # already met

            if cond.startswith("tool:"):
                # e.g. "tool:check_order_status called"
                tool_name = cond.split(":")[1].split()[0]
                if (action.action_type == "call_tool"
                        and action.tool_name == tool_name
                        and tool_result
                        and tool_result.get("success")):
                    self._success_flags[cond] = True

            elif cond == "refund_processed":
                if self._refund_processed:
                    self._success_flags[cond] = True

            elif cond == "escalation_done":
                if self._escalation_done:
                    self._success_flags[cond] = True

            elif cond == "emotion_reduced":
                if self._current_emotion < self._task["initial_emotion"]:
                    self._success_flags[cond] = True

            elif cond.startswith("response_contains:"):
                # e.g. "response_contains:order status"
                keyword = cond.split(":", 1)[1]
                if action.action_type == "respond" and action.message:
                    if keyword.lower() in action.message.lower():
                        self._success_flags[cond] = True
