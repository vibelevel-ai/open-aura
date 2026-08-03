"""VibeLevel Aura — scoring model, CODING modality (referenceless).

Scoring is **referenceless** — there are no rubric/requirements/test-cases,
since real work has none. We score the human's PROCESS and COLLABORATION as
evidenced in the transcript + the work produced.

Scored dimensions:
  prompting, ai_pairing, human_contribution   → chat-only / meta
  product_thinking, design_thinking            → judged from transcript/work
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MODALITY = "coding"

# Framing injected into the scoring prompt: there is no goal/rubric, and its
# absence must not be penalised.
AURA_PROMPT_FRAMING = (
    "You are evaluating a REAL, self-directed AI-assisted work session. There is "
    "NO assessment, NO rubric, NO stated requirements, and NO test cases. Do NOT "
    "penalise the absence of a defined goal or acceptance criteria. Judge ONLY "
    "the quality of the human's process and collaboration with the AI, as "
    "evidenced in the transcript and the work produced. Score each dimension 0-10 "
    "against its sub_criteria. Where evidence is thin or ambiguous, score "
    "conservatively rather than assuming competence."
)

AURA_SCORING_MODEL_CODING: Dict[str, Any] = {
    "version": "aura-1.0c",
    "modality": MODALITY,
    "prompt_framing": AURA_PROMPT_FRAMING,
    "dimensions": {
        "prompting": {
            "name": "Prompting Effectiveness",
            "description": "How clearly the human communicates intent, context, and constraints to the AI.",
            "weight": 25,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "evidence_sources": ["chat_history"],
            "sub_criteria": [
                "Clarity & specificity of requests",
                "Providing relevant context and constraints",
                "Task structuring & decomposition",
                "Effective follow-up and refinement",
            ],
        },
        "ai_pairing": {
            "name": "AI Collaboration",
            "description": "How well the human steers, iterates with, and course-corrects the AI.",
            "weight": 30,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "evidence_sources": ["chat_history"],
            "sub_criteria": [
                "Goal-setting and direction with the AI",
                "Steering toward desired outcomes",
                "Iterating rather than accepting first output",
                "Course-correction when the AI misunderstands",
                "Healthy reliance vs over-reliance",
            ],
        },
        "product_thinking": {
            "name": "Product Thinking",
            "description": "Reasoning about user outcomes and the right solution (judged from the transcript, not a rubric).",
            "weight": 22,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Frames work in terms of user/product outcomes",
                "Drives the AI toward the RIGHT solution, not just any",
                "Considers edge cases and real-world constraints",
                "Validates behaviour rather than assuming",
            ],
        },
        "design_thinking": {
            "name": "Problem Solving & Design",
            "description": "Architectural and decomposition reasoning evident in how the work was approached.",
            "weight": 23,
            "max_score": 10.0,
            "status": "mvp",
            "category": "craft",
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Decomposes problems before delegating",
                "Considers structure/architecture, not just local fixes",
                "Sequences work sensibly (plan → build)",
                "Trade-off awareness",
            ],
        },
        "human_contribution": {
            "name": "Human Contribution vs AI Reliance",
            "description": "Overall independent initiative and original thinking vs passively accepting AI output. Meta-label; unweighted.",
            "weight": 0,
            "weighted": False,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "classification": {
                "levels": [
                    {"label": "Passive Delegator", "range": [0, 5], "description": "High AI use, low human input."},
                    {"label": "Balanced Builder", "range": [5.01, 7], "description": "Mix of AI and manual direction."},
                    {"label": "Active Contributor", "range": [7.01, 9], "description": "Steers, validates, iterates."},
                    {"label": "Vibe Coder", "range": [9.01, 10], "description": "High AI use AND high human initiative — AI as force multiplier."},
                ]
            },
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Direction-setting and independent decisions",
                "Original ideas introduced by the human",
                "Critically evaluating / rejecting / modifying AI suggestions",
                "Ratio of human-originated vs passively-accepted work",
            ],
        },
    },
    # Aura Score bands.
    "levels": [
        {"name": "Emerging", "min_score": 0.0, "max_score": 3.0},
        {"name": "Capable", "min_score": 3.0, "max_score": 6.0},
        {"name": "Strong", "min_score": 6.0, "max_score": 8.0},
        {"name": "Exceptional", "min_score": 8.0, "max_score": 10.01},
    ],
    "dampening_rules": {
        "description": "Cap craft-dimension scores when engagement (transcript substance) is low.",
        "engagement_thresholds": {
            "low": {"max_output_score": 4.0, "explanation": "Low engagement caps craft dims at 4.0."},
            "moderate": {"max_output_score": 7.0, "explanation": "Moderate engagement caps craft dims at 7.0."},
            "high": {"max_output_score": 10.0, "explanation": "No cap."},
        },
        # Process dims (prompting, ai_pairing) are NOT capped — they read the
        # prompts that exist. Craft dims need substance to credibly score high.
        "output_quality_dimensions": ["product_thinking", "design_thinking"],
    },
    # ----- Archetype catalog (coding). Grounded in the Human Contribution spectrum
    # (NOT Paxel work-habits): assignment is HC-driven (see assign_archetype in the
    # signal extractor), with the dominant scored dimension breaking the mid-band. -----
    "archetypes": [
        {"id": "delegator", "name": "The Delegator",
         "tagline": "Hands the wheel to the AI, steers lightly, takes what it ships.",
         "signature_dimensions": [], "signature_signals": []},
        {"id": "collaborator", "name": "The Collaborator",
         "tagline": "Pairs tightly with the AI — steers, redirects, and iterates until it's right.",
         "signature_dimensions": ["ai_pairing", "prompting"], "signature_signals": ["redirect_rate"]},
        {"id": "director", "name": "The Director",
         "tagline": "Sets crisp intent up front, frames the problem cleanly, lets the AI execute.",
         "signature_dimensions": ["prompting"], "signature_signals": ["plan_ratio"]},
        {"id": "product_builder", "name": "The Product Builder",
         "tagline": "Builds toward outcomes — every move serves the user, not just the output.",
         "signature_dimensions": ["product_thinking"], "signature_signals": []},
        {"id": "architect", "name": "The Architect",
         "tagline": "Plans first, codifies decisions, builds scaffolding that compounds.",
         "signature_dimensions": ["design_thinking", "product_thinking"], "signature_signals": ["plan_ratio"]},
        {"id": "craftsperson", "name": "The Craftsperson",
         "tagline": "Shapes every detail — design and product taste applied to the smallest decision.",
         "signature_dimensions": ["design_thinking", "product_thinking"], "signature_signals": []},
        {"id": "vibe_coder", "name": "The Vibe Coder",
         "tagline": "Peak human contribution, balanced excellence — the AI is pure force-multiplier.",
         "signature_dimensions": ["design_thinking", "product_thinking", "ai_pairing", "prompting"], "signature_signals": []},
    ],
    # ----- Card-signal taxonomy. Source: 'telemetry' (deterministic, no LLM),
    # 'score' (from dimensions), or 'llm' (qualitative pass). The signal extractor
    # computes telemetry/score cards; the scoring service fills llm cards. -----
    "card_signals": [
        # credibility (hiring-facing)
        {"id": "plan_ratio", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How often do you plan?", "template": "{pct}% plan-first — you scaffold before building."},
        {"id": "redirect_rate", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How do you steer?", "template": "You steer hard — {n} redirects in 10 prompts."},
        {"id": "parallel_agents", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How many agents do you run?", "template": "{n} AI agents orchestrated."},
        {"id": "human_token_share", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How much do you write?", "template": "You write {pct}% of the tokens."},
        {"id": "top_dimension", "klass": "credibility", "source": "score", "scope": "overall",
         "question": "What's your strongest skill?", "template": "{dim} — {score}/10, your top dimension."},
        # personality (shareable)
        {"id": "token_footprint", "klass": "personality", "source": "telemetry", "scope": "both",
         "question": "What's your token footprint?", "template": "~{tokens} tokens {per}."},
        {"id": "model_mix", "klass": "personality", "source": "telemetry", "scope": "overall",
         "question": "Which model do you use most?", "template": "Your go-to model — {model}."},
        {"id": "tools_used", "klass": "personality", "source": "telemetry", "scope": "both",
         "question": "What's in your toolbelt?", "template": "{distinct} tools, {n} calls — {top}."},
        {"id": "skills_used", "klass": "personality", "source": "telemetry", "scope": "both",
         "question": "Which skills do you tap?", "template": "Tapped {n} skill(s) — {top}."},
        {"id": "time_of_day", "klass": "personality", "source": "telemetry", "scope": "overall",
         "question": "When are you most productive?", "template": "{label} — {pct}% of work {window}."},
        {"id": "prompt_length", "klass": "personality", "source": "telemetry", "scope": "both",
         "question": "How long are your prompts?", "template": "{label} — avg {n} words per prompt."},
        {"id": "politeness", "klass": "personality", "source": "telemetry", "scope": "overall",
         "question": "How polite are you to your agent?", "template": "You said thanks {n} times."},
        {"id": "go_to_phrase", "klass": "personality", "source": "llm", "scope": "overall",
         "question": "What's your go-to prompt?", "template": "“{phrase}” — your most-used phrase."},
        {"id": "signature", "klass": "personality", "source": "llm", "scope": "both",
         "question": "Your signature move?", "template": "{phrase}"},
        {"id": "growth_edge", "klass": "credibility", "source": "llm", "scope": "both",
         "question": "Your growth edge?", "template": "{phrase}"},
    ],
}

_VERSION_ORDER = {"mvp": 0, "v1": 1, "v2": 2, "disabled": 99}


def get_active_dimensions(version: str = "mvp") -> Dict[str, Dict[str, Any]]:
    max_order = _VERSION_ORDER.get(version, 0)
    return {
        k: d for k, d in AURA_SCORING_MODEL_CODING["dimensions"].items()
        if _VERSION_ORDER.get(d["status"], 99) <= max_order
    }


def get_dimension_weights(dimensions: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    weighted = {k: d for k, d in dimensions.items() if d.get("weight", 0) > 0 and d.get("weighted", True)}
    total = sum(d["weight"] for d in weighted.values())
    return {k: d["weight"] / total for k, d in weighted.items()} if total else {}


def get_aura_label(score: float) -> str:
    for level in AURA_SCORING_MODEL_CODING["levels"]:
        if level["min_score"] <= score < level["max_score"]:
            return level["name"]
    raise ValueError(f"Aura score {score} could not be mapped to a band.")


def get_all_dimension_keys() -> List[str]:
    return list(AURA_SCORING_MODEL_CODING["dimensions"].keys())


def get_model_version() -> str:
    return AURA_SCORING_MODEL_CODING["version"]


def get_dampening_rules() -> Dict[str, Any]:
    return AURA_SCORING_MODEL_CODING["dampening_rules"]


def get_archetypes() -> List[Dict[str, Any]]:
    return AURA_SCORING_MODEL_CODING["archetypes"]


def get_card_signals() -> List[Dict[str, Any]]:
    return AURA_SCORING_MODEL_CODING["card_signals"]


def get_human_contribution_label(score: float) -> str:
    hc = AURA_SCORING_MODEL_CODING["dimensions"].get("human_contribution", {})
    for level in hc.get("classification", {}).get("levels", []):
        lo, hi = level["range"]
        if lo <= score <= hi:
            return level["label"]
    return "Unknown"


def get_hc_score_cap(hc_score: float) -> float:
    """Overall-score ceiling implied by the human-contribution band the score
    falls into: the overall Aura can't exceed the ceiling of your HC band. The
    top band (Vibe Coder) is uncapped. Simple anti-gaming coupling — a great
    prompt with little real human contribution can't buy a high overall score.
    Derived from the HC classification bands so it stays in sync with them."""
    levels = (AURA_SCORING_MODEL_CODING["dimensions"]
              .get("human_contribution", {})
              .get("classification", {}).get("levels", []))
    for i, level in enumerate(levels):
        lo, hi = level["range"]
        if lo <= hc_score <= hi:
            return 10.0 if i == len(levels) - 1 else float(hi)
    return 10.0
