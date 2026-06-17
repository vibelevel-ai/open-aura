"""VibeLevel Aura — scoring model, NON-CODING (writing) modality (referenceless).

Scoring is **referenceless** — there are no rubric/requirements/deliverable
spec, since real work has none. We score the human's PROCESS and COLLABORATION
as evidenced in the transcript + the work produced, judging deliverable quality
INTRINSICALLY (no rubric to measure against).

Scored dimensions:
  prompting, ai_pairing, human_contribution    → chat-only / meta
  strategic_thinking, structured_thinking       → judged from transcript/work
  deliverable_quality                           → judged INTRINSICALLY:
                                                  is the artifact itself good?

This MIRRORS `aura_model_coding.py` in structure and getter API; only the
dimension set, archetypes, and card signals differ (non-coding flavour).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MODALITY = "noncoding"

# Framing injected into the scoring prompt: there is no goal/rubric, and its
# absence must not be penalised. For non-coding, deliverable quality is judged
# on its own merits, not against a spec.
AURA_PROMPT_FRAMING = (
    "You are evaluating a REAL, self-directed AI-assisted work session (writing, "
    "strategy, research, analysis, or other non-coding knowledge work). There is "
    "NO assessment, NO rubric, NO stated requirements, and NO deliverable spec. Do "
    "NOT penalise the absence of a defined goal or acceptance criteria. Judge the "
    "deliverable's quality INTRINSICALLY — is the artifact itself clear, well-"
    "reasoned, and useful — not against any required output. Score ONLY the quality "
    "of the human's process, collaboration with the AI, and the work produced, as "
    "evidenced in the transcript and the artifacts. Score each dimension 0-10 "
    "against its sub_criteria. Where evidence is thin or ambiguous, score "
    "conservatively rather than assuming competence."
)

AURA_SCORING_MODEL_WRITING: Dict[str, Any] = {
    "version": "aura-1.0w",
    "modality": MODALITY,
    "prompt_framing": AURA_PROMPT_FRAMING,
    "dimensions": {
        "prompting": {
            "name": "Prompting Effectiveness",
            "description": "How clearly the human communicates intent, context, and constraints to the AI.",
            "weight": 20,
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
            "weight": 25,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "evidence_sources": ["chat_history"],
            "sub_criteria": [
                "Goal-setting and direction with the AI",
                "Steering toward desired outcomes",
                "Iterating rather than accepting first draft",
                "Course-correction when the AI misunderstands",
                "Healthy reliance vs over-reliance",
            ],
        },
        "strategic_thinking": {
            "name": "Strategic Thinking",
            "description": "Market awareness, audience perspective, and strategic depth (judged from the transcript and work, not a rubric).",
            "weight": 20,
            "max_score": 10.0,
            "status": "mvp",
            "category": "human_effort",
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Frames work in terms of audience/market outcomes",
                "Drives the AI toward the RIGHT angle, not just any output",
                "Competitive awareness and positioning",
                "Data-driven or evidence-based reasoning",
            ],
        },
        "structured_thinking": {
            "name": "Structured Thinking",
            "description": "Logical structure, framework application, and problem decomposition evident in how the work was approached.",
            "weight": 15,
            "max_score": 10.0,
            "status": "mvp",
            "category": "craft",
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Decomposes problems before delegating",
                "Uses frameworks (SWOT, MECE, etc.) where appropriate",
                "Clear hierarchy and logical flow of information",
                "Sequences work sensibly (outline → draft)",
            ],
        },
        "deliverable_quality": {
            "name": "Deliverable Quality",
            "description": "How good the produced artifact is ON ITS OWN MERITS — clarity, depth, professionalism — judged intrinsically, NOT against a rubric.",
            "weight": 20,
            "max_score": 10.0,
            "status": "mvp",
            "category": "craft",
            "evidence_sources": ["chat_history", "work_files"],
            "sub_criteria": [
                "Clarity, tone, and persuasiveness of the writing",
                "Appropriate level of detail and depth",
                "Professional formatting and presentation",
                "Actionable recommendations or next steps",
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
                    {"label": "Passive Delegator", "range": [0, 3], "description": "High AI use, low human input."},
                    {"label": "Balanced Builder", "range": [3.01, 5], "description": "Mix of AI and manual direction."},
                    {"label": "Active Contributor", "range": [5.01, 7], "description": "Steers, validates, iterates."},
                    {"label": "Vibe Coder", "range": [7.01, 10], "description": "High AI use AND high human initiative — AI as force multiplier."},
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
        "output_quality_dimensions": ["strategic_thinking", "structured_thinking", "deliverable_quality"],
    },
    # ----- Archetype catalog (non-coding). Grounded in the Human Contribution
    # spectrum (NOT Paxel work-habits): assignment is HC-driven (see assign_archetype
    # in the signal extractor), with the dominant scored dimension breaking the mid-band. -----
    "archetypes": [
        {"id": "delegator", "name": "The Delegator",
         "tagline": "Hands the pen to the AI, steers lightly, takes what it drafts.",
         "signature_dimensions": [], "signature_signals": []},
        {"id": "collaborator", "name": "The Co-writer",
         "tagline": "Writes shoulder-to-shoulder with the AI — steers, redirects, and revises until it sings.",
         "signature_dimensions": ["ai_pairing", "prompting"], "signature_signals": ["redirect_rate"]},
        {"id": "director", "name": "The Director",
         "tagline": "Sets crisp intent up front, frames the brief cleanly, lets the AI draft.",
         "signature_dimensions": ["prompting"], "signature_signals": ["outline_ratio"]},
        {"id": "strategist", "name": "The Strategist",
         "tagline": "Thinks in audience and positioning — every word earns its place in the argument.",
         "signature_dimensions": ["strategic_thinking"], "signature_signals": []},
        {"id": "structurer", "name": "The Architect",
         "tagline": "Outlines first, imposes logical structure, turns the messy into the clear.",
         "signature_dimensions": ["structured_thinking", "strategic_thinking"], "signature_signals": ["outline_ratio"]},
        {"id": "craftsperson", "name": "The Wordsmith",
         "tagline": "Shapes every sentence — structure and polish applied to the smallest phrase.",
         "signature_dimensions": ["deliverable_quality", "structured_thinking"], "signature_signals": []},
        {"id": "vibe_writer", "name": "The Vibe Writer",
         "tagline": "Peak human contribution, balanced excellence — the AI is pure force-multiplier.",
         "signature_dimensions": ["strategic_thinking", "structured_thinking", "deliverable_quality", "ai_pairing", "prompting"], "signature_signals": []},
    ],
    # ----- Card-signal taxonomy. Source: 'telemetry' (deterministic, no LLM),
    # 'score' (from dimensions), or 'llm' (qualitative pass). The signal extractor
    # computes telemetry/score cards; the scoring service fills llm cards.
    # Coding-only signals dropped (parallel_agents); verify_habit reframed as
    # revision_habit; plan_ratio reframed as outline_ratio. -----
    "card_signals": [
        # credibility (hiring-facing)
        {"id": "outline_ratio", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How often do you outline first?", "template": "{pct}% outline-first — you structure before drafting."},
        {"id": "redirect_rate", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "How do you steer?", "template": "You steer hard — {n} redirects in 10 prompts."},
        {"id": "revision_habit", "klass": "credibility", "source": "telemetry", "scope": "both",
         "question": "Do you revise your work?", "template": "You revise/refine in {pct}% of sessions."},
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
        k: d for k, d in AURA_SCORING_MODEL_WRITING["dimensions"].items()
        if _VERSION_ORDER.get(d["status"], 99) <= max_order
    }


def get_dimension_weights(dimensions: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    weighted = {k: d for k, d in dimensions.items() if d.get("weight", 0) > 0 and d.get("weighted", True)}
    total = sum(d["weight"] for d in weighted.values())
    return {k: d["weight"] / total for k, d in weighted.items()} if total else {}


def get_aura_label(score: float) -> str:
    for level in AURA_SCORING_MODEL_WRITING["levels"]:
        if level["min_score"] <= score < level["max_score"]:
            return level["name"]
    raise ValueError(f"Aura score {score} could not be mapped to a band.")


def get_all_dimension_keys() -> List[str]:
    return list(AURA_SCORING_MODEL_WRITING["dimensions"].keys())


def get_model_version() -> str:
    return AURA_SCORING_MODEL_WRITING["version"]


def get_dampening_rules() -> Dict[str, Any]:
    return AURA_SCORING_MODEL_WRITING["dampening_rules"]


def get_archetypes() -> List[Dict[str, Any]]:
    return AURA_SCORING_MODEL_WRITING["archetypes"]


def get_card_signals() -> List[Dict[str, Any]]:
    return AURA_SCORING_MODEL_WRITING["card_signals"]


def get_human_contribution_label(score: float) -> str:
    hc = AURA_SCORING_MODEL_WRITING["dimensions"].get("human_contribution", {})
    for level in hc.get("classification", {}).get("levels", []):
        lo, hi = level["range"]
        if lo <= score <= hi:
            return level["label"]
    return "Unknown"
