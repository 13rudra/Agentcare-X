"""
AgentCare X — Deterministic Grader

End-of-episode evaluation. Computes a 0.0–1.0 score based on:
  - Resolution correctness (40%)
  - Tool usage accuracy  (25%)
  - Emotional intelligence (20%)
  - Efficiency            (15%)

All scoring is rule-based with zero randomness.
"""

from __future__ import annotations

from models import EnvState
from env.customer import RUDE_KEYWORDS


class TaskGrader:
    """Deterministic grader for a single episode."""

    def __init__(self, task_meta: dict) -> None:
        self.task = task_meta

    def grade(self, final_state: EnvState) -> dict[str, float]:
        """
        Grade the episode. Returns dict with sub-scores and final_score, all 0.0–1.0.
        """
        resolution = self._score_resolution(final_state)
        tool_usage = self._score_tool_usage(final_state)
        emotional_iq = self._score_emotional_iq(final_state)
        efficiency = self._score_efficiency(final_state)

        final_score = (
            0.40 * resolution
            + 0.25 * tool_usage
            + 0.20 * emotional_iq
            + 0.15 * efficiency
        )

        return {
            "resolution": round(resolution, 4),
            "tool_usage": round(tool_usage, 4),
            "emotional_iq": round(emotional_iq, 4),
            "efficiency": round(efficiency, 4),
            "final_score": round(final_score, 4),
        }

    # ------------------------------------------------------------------
    # Sub-scores
    # ------------------------------------------------------------------

    def _score_resolution(self, state: EnvState) -> float:
        """
        1.0 if all success conditions met (resolved=True).
        Partial credit based on fraction of conditions met.
        """
        conditions = self.task["success_conditions"]
        if not conditions:
            return 1.0

        tools_called = {tc["tool"] for tc in state.tool_calls_made if tc.get("result", {}).get("success")}
        emotion_reduced = (
            state.emotion_history[-1] < self.task["initial_emotion"]
            if state.emotion_history
            else False
        )

        met = 0
        for cond in conditions:
            if cond.startswith("tool:"):
                tool_name = cond.split(":")[1].split()[0]
                if tool_name in tools_called:
                    met += 1
            elif cond == "refund_processed":
                if any(tc["tool"] == "process_refund" and tc.get("result", {}).get("success")
                       for tc in state.tool_calls_made):
                    met += 1
            elif cond == "escalation_done":
                if any(tc["tool"] == "escalate_to_manager" and tc.get("result", {}).get("success")
                       for tc in state.tool_calls_made):
                    met += 1
            elif cond == "emotion_reduced":
                if emotion_reduced:
                    met += 1

        return met / len(conditions)

    def _score_tool_usage(self, state: EnvState) -> float:
        """
        Fraction of required tools called successfully.
        Deduct 0.1 per unnecessary tool call (clamped >= 0).
        """
        required = self.task["required_tools"]
        successful_tools = [
            tc["tool"] for tc in state.tool_calls_made
            if tc.get("result", {}).get("success")
        ]
        called_required = [t for t in required if t in successful_tools]
        base = len(called_required) / len(required) if required else 1.0

        # Count unnecessary calls
        unnecessary = sum(1 for t in successful_tools if t not in required)
        penalty = unnecessary * 0.1

        return max(0.0, base - penalty)

    def _score_emotional_iq(self, state: EnvState) -> float:
        """
        1.0 if emotion decreased AND no rude language detected.
        0.5 if emotion unchanged.
        0.0 if emotion increased or rude language found.
        """
        if not state.emotion_history or len(state.emotion_history) < 2:
            return 0.5

        initial = state.emotion_history[0]
        final = state.emotion_history[-1]

        # Check for rude keywords in agent messages
        rude_found = False
        for msg in state.conversation_history:
            if msg["role"] == "agent" and not msg["content"].startswith("[Tool:"):
                lower = msg["content"].lower()
                if any(kw in lower for kw in RUDE_KEYWORDS):
                    rude_found = True
                    break

        if rude_found:
            return 0.0
        if final < initial:
            return 1.0
        if abs(final - initial) < 0.01:
            return 0.5
        return 0.0  # emotion increased

    def _score_efficiency(self, state: EnvState) -> float:
        """
        max(0, 1.0 - (actual_steps - expected_steps) / max_steps)
        """
        expected = self.task["expected_steps"]
        max_steps = self.task.get("max_steps", 10)
        actual = state.step_count

        if actual <= expected:
            return 1.0

        score = 1.0 - (actual - expected) / max_steps
        return max(0.0, score)
