"""
AgentCare X — Customer Simulator

Deterministic customer response model.
Generates customer messages and emotion updates based on scenario, step, and agent behavior.
All logic is rule-based with zero randomness.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Empathy / rudeness keyword lists (used for tone detection)
# ---------------------------------------------------------------------------

EMPATHY_KEYWORDS: set[str] = {
    "sorry", "apologize", "apologies", "understand", "understand your frustration",
    "help", "assist", "right away", "certainly", "absolutely",
    "inconvenience", "bear with", "patience", "appreciate",
    "let me", "i will", "i'll", "resolve", "fix", "take care",
}

RUDE_KEYWORDS: set[str] = {
    "not my problem", "deal with it", "whatever", "calm down",
    "you're wrong", "that's your fault", "too bad", "i don't care",
    "stop complaining", "nothing i can do", "not possible",
}


def detect_empathy(message: str) -> bool:
    """Return True if the message contains empathy keywords."""
    lower = message.lower()
    return any(kw in lower for kw in EMPATHY_KEYWORDS)


def detect_rudeness(message: str) -> bool:
    """Return True if the message contains rude/dismissive language."""
    lower = message.lower()
    return any(kw in lower for kw in RUDE_KEYWORDS)


# ---------------------------------------------------------------------------
# Emotion update logic
# ---------------------------------------------------------------------------

def compute_emotion_delta(
    agent_message: str | None,
    action_type: str,
    tool_success: bool | None,
    current_emotion: float,
    # NEW — optional LLM-judge empathy score (0.0–1.0)
    empathy_score: float | None = None,
) -> float:
    """
    Compute the change in customer emotion based on agent behavior.

    Returns a float delta (negative = calming, positive = agitating).
    Result is deterministic given the same inputs.

    If empathy_score is provided (from LLM judge), it's used instead of
    the keyword-based boolean for a more nuanced calming effect.
    """
    delta = 0.0

    if action_type == "respond" and agent_message:
        # NEW — use LLM judge score if available, else fall back to keywords
        if empathy_score is not None:
            # Scale: score 1.0 → -0.15 (very calming), score 0.0 → +0.05 (slightly agitating)
            delta += 0.05 - (empathy_score * 0.20)
        else:
            if detect_empathy(agent_message):
                delta -= 0.10
            # Generic/short response without empathy
            if not detect_empathy(agent_message) and len(agent_message) < 20:
                delta += 0.05

        if detect_rudeness(agent_message):
            delta += 0.20

    if action_type == "call_tool":
        if tool_success is True:
            delta -= 0.20  # resolved something → customer calms
        elif tool_success is False:
            delta += 0.05  # tool error → slight frustration

    # If agent only calls tools without ever responding, slight annoyance
    if action_type == "call_tool" and agent_message is None:
        delta += 0.02

    return delta


def clamp_emotion(emotion: float) -> float:
    """Clamp emotion to [0.0, 1.0]."""
    return max(0.0, min(1.0, emotion))


# ---------------------------------------------------------------------------
# Customer message templates
# ---------------------------------------------------------------------------

# Keys: (task_id, step_index) → message
# Fallback: generic follow-up if step_index exceeds templates

_TEMPLATES: dict[tuple[str, int], str] = {
    # Task 1 — Easy: Order lookup
    ("easy", 0): "Hi, I placed an order a few days ago and I'm wondering where it is. Can you look into it for me?",
    ("easy", 1): "Thanks! Can you tell me when it will arrive?",
    ("easy", 2): "Great, that's all I needed. Thank you!",

    # Task 2 — Medium: Angry customer + refund
    ("medium", 0): "I've been waiting FOREVER for my order and it's still not here! This is completely unacceptable!",
    ("medium", 1): "Well, what are you going to DO about it? I want my money back!",
    ("medium", 2): "Fine. Process the refund then. I'm really frustrated with this service.",
    ("medium", 3): "Is the refund confirmed? When will I get my money?",
    ("medium", 4): "Okay. I hope this gets resolved quickly.",

    # Task 3 — Hard: Wrong item + refund + escalation
    ("hard", 0): "I received a COMPLETELY WRONG item! I ordered a laptop and got headphones instead! I am FURIOUS!",
    ("hard", 1): "Check my order right now! This is ridiculous!",
    ("hard", 2): "I want a full refund AND I want to speak to a manager about this!",
    ("hard", 3): "Have you processed the refund? I'm still waiting!",
    ("hard", 4): "I also want this escalated to your manager. This level of incompetence is unbelievable!",
    ("hard", 5): "Is the escalation confirmed? I want a ticket number.",
    ("hard", 6): "Fine. I expect this to be fully resolved.",

    # NEW — Task 4: Out of Stock
    ("out_of_stock", 0): "I placed an order for a camera last week and now I'm told it's out of stock?! What's going on?",
    ("out_of_stock", 1): "Can you check if it's going to be restocked? I need it soon!",
    ("out_of_stock", 2): "Are there any alternatives I can get instead?",
    ("out_of_stock", 3): "What about a discount if I wait for the restock?",
    ("out_of_stock", 4): "Okay, I'll consider the options. Thanks.",

    # NEW — Task 5: Subscription Management
    ("subscription", 0): "I want to cancel my subscription. I'm paying for features I never use and it's a waste of money!",
    ("subscription", 1): "Can you look up my subscription and tell me what I'm actually paying for?",
    ("subscription", 2): "What happens if I cancel mid-cycle? Do I get a refund for the remaining days?",
    ("subscription", 3): "Is there a cheaper plan or a discount you can offer? Maybe I'll stay if the price is right.",
    ("subscription", 4): "Alright, let me think about it. Apply that discount for now.",
    ("subscription", 5): "Okay, I'll keep the subscription with the discount. Thanks for your help.",
}

# Follow-ups when customer has nothing specific left
_FOLLOWUP_CALM = "Okay, is there anything else?"
_FOLLOWUP_RESOLVED = "Thank you for your help."

# NEW — scenario-specific frustrated fallback messages
_FOLLOWUP_FRUSTRATED_BY_TASK: dict[str, str] = {
    "easy":          "Are you going to help me or not?!",
    "medium":        "I've been waiting 2 weeks for my refund, this is unacceptable!",
    "hard":          "I want to speak to your manager right now.",
    "out_of_stock":  "I needed this for a gift, what am I supposed to do now?",
    "subscription":  "I'm being charged for something I don't even use anymore!",
}

# Default fallback for unknown task IDs
_FOLLOWUP_FRUSTRATED_DEFAULT = "Are you going to help me or not?!"


def get_customer_message(task_id: str, step_index: int, emotion: float, resolved: bool) -> str:
    """
    Return the deterministic customer message for a given task + step.

    Falls back to scenario-specific frustrated messages if beyond the scripted messages.
    """
    if resolved:
        return _FOLLOWUP_RESOLVED

    key = (task_id, step_index)
    if key in _TEMPLATES:
        return _TEMPLATES[key]

    # NEW — scenario-specific fallback based on emotion
    if emotion >= 0.6:
        return _FOLLOWUP_FRUSTRATED_BY_TASK.get(task_id, _FOLLOWUP_FRUSTRATED_DEFAULT)
    return _FOLLOWUP_CALM
