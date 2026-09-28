"""J13 v2 task 1: per-action confidence thresholds.

Adapted from the confidence-gated routing pattern documented in Simon
Scrapes' Jev walkthrough (yt-2dai1jvyd5m, archived): one confidence
threshold PER ACTION, set by the cost of being wrong — not one global gate.

Actions in Tierllama (what the router DOES next, action-first rule):
- query / read-only chat  -> cheapest to be wrong (worst case: a bad answer)  -> 0.60
- schedule a job          -> wrong date = work runs at the wrong time        -> 0.85
- destructive / dispatch-now on someone's behalf (future: cancel, overwrite,
  send-as-user)           -> worst case: irreversible damage                 -> 0.95

The clarify-or-ask rule is absolute and unchanged: below threshold -> ask,
never silently guess.
"""
import json
from pathlib import Path

# Per-action table (J13 v2). Keys are ACTIONS, not message features.
# `when` keeps the scheduler's date-gate on the schedule action.
ACTIONS = {
    "query":     {"conf_threshold": 0.60, "description": "read-only chat, answer-only actions"},
    "schedule":  {"conf_threshold": 0.85, "description": "enter a job in the scheduler with a due date"},
    "destructive": {"conf_threshold": 0.95, "description": "irreversible/destructive actions (future: cancel, overwrite, send-as-user)"},
}

# message action -> table key. Dispatch-now of a normal task is a query-scale
# action (worst case = a wrong answer, retryable); scheduling is the riskier one.
ACTION_FOR_LANE = {
    "LOCAL": "query", "CLOUD_MEDIUM": "query", "CLOUD_HARD": "query",
    "BOX": "query", "FALLBACK": "query",
}

def action_conf_threshold(action: str) -> float:
    """Threshold for an action key; unknown action -> safest (0.95)."""
    a = ACTIONS.get(action)
    return a["conf_threshold"] if a else ACTIONS["destructive"]["conf_threshold"]

def gate(action: str, confidence: float) -> str:
    """Per-action clarify gate. Returns 'proceed' | 'clarify'.
    Below threshold is ALWAYS clarify (never guess-execute)."""
    return "proceed" if confidence >= action_conf_threshold(action) else "clarify"

def resolve_action(when: str | None, lane: str | None) -> str:
    """Map the router's decision context to an action key.
    Scheduling (DEADLINE) is the schedule action; everything else dispatches
    (query-scale for now; destructive reserved for future cancels/overwrites)."""
    if when == "DEADLINE":
        return "schedule"
    return ACTION_FOR_LANE.get(lane or "", "query")