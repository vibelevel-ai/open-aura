"""VibeLevel Aura — referenceless scoring service (the concrete `AuraScorer`).

  - LLM client:  `core.model_config.model_config_manager.create_llm(...)`
                 invoked off-thread via `asyncio.to_thread`.
  - DB:          `core.database_sync.get_pool()` (psycopg2, RealDictCursor).
  - Model defs:  `aura_model_coding` / `aura_model_writing` (selected by modality).
  - Signals:     `aura_signal_extractor` (fingerprint / modality / cards / archetype).

The whole point of Aura is REFERENCELESS scoring: there is no rubric, no
requirements, no test cases. We feed the model only the transcript excerpts +
a files-touched summary, and ask it to judge the human's process/collaboration.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from ...core.database_sync import get_pool
from .contracts import (
    AuraScorer,
    Card,
    DimensionScore,
    EvidencePacket,
    ScoreResult,
)
from . import aura_model_coding
from . import aura_model_writing
from .aura_signal_extractor import (
    MODALITY_CODING,
    assign_archetype,
    build_session_cards,
    classify_modality,
    session_fingerprint,
)
from .pfg_client import ground_session as pfg_ground_session

logger = logging.getLogger(__name__)

# Scoring LLM model — configurable.
AURA_SCORING_MODEL = os.getenv("AURA_SCORING_MODEL", "openai/gpt-oss-120b")

# Safety guardrails on prompt size.
MAX_TURNS = 200          # transcript excerpts fed to the model
MAX_EXCERPT_CHARS = 2000  # per-turn truncation (excerpts are already redacted)
MAX_FILES = 80           # files-touched summary lines
MAX_IMPORT_BATCH = 100   # import_sessions cap
# Bounded parallelism for bulk import — number of sessions scored concurrently.
# Each concurrent score is one (off-thread) LLM call; the sidecar pool maxes at
# 20 conns and each score holds at most one brief conn, so 5 is comfortably safe.
IMPORT_CONCURRENCY = max(1, int(os.getenv("AURA_IMPORT_CONCURRENCY", "5")))


# ---------------------------------------------------------------------------
# Model-module selection (coding vs writing/noncoding share one getter API)
# ---------------------------------------------------------------------------

def _model_module(modality: str):
    """Return the model-definition module for a modality.

    Both modules expose the SAME getter surface (get_active_dimensions,
    get_dimension_weights, get_aura_label, get_model_version,
    get_dampening_rules, get_human_contribution_label, AURA_PROMPT_FRAMING).
    """
    if modality == "noncoding":
        return aura_model_writing
    return aura_model_coding


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AuraScoringService(AuraScorer):
    """Concrete implementation of the `AuraScorer` protocol (contracts.py)."""

    # -- public API ---------------------------------------------------------

    async def score_evidence(
        self, user_id: str, evidence: EvidencePacket, local_context=None
    ) -> ScoreResult:
        """Score one real AI work session, referencelessly.

        Pipeline: classify modality -> select model -> build referenceless
        prompt -> call LLM -> parse dimension scores + qualitative cards ->
        weighted overall -> engagement dampening -> labels -> cards ->
        persist AuraSession (upsert on (user_id, fingerprint)) -> profile_delta.

        ``local_context`` (Open Aura only) is the UNREDACTED real diff/transcript,
        used solely for best-effort PFG operational grounding. It is NOT scored,
        persisted, or fingerprinted.
        """
        fingerprint = session_fingerprint(evidence)
        ingested_via = "mcp"
        result = await self._score_one(
            user_id=user_id,
            evidence=evidence,
            fingerprint=fingerprint,
            ingested_via=ingested_via,
        )
        # Best-effort PFG grounding → advisory check-tips (operational insights).
        # Single-session only (NOT bulk import). Off by default + env-gated; runs
        # off-thread (the extractor's LLM call + urllib transport are blocking);
        # never affects the score and never raises.
        if local_context is not None:
            try:
                tips = await asyncio.to_thread(
                    pfg_ground_session, local_context, evidence
                )
                if tips:
                    result["pfg_check_tips"] = tips
            except Exception as exc:
                logger.debug("[AURA-PFG] grounding skipped: %s", exc)
        return result

    async def import_sessions(
        self, user_id: str, packets: List[EvidencePacket]
    ) -> List[ScoreResult]:
        """Bulk one-shot history import — scored CONCURRENTLY (bounded).

        Dedups packets whose fingerprint already exists for the user, then scores
        the rest in parallel (``IMPORT_CONCURRENCY`` at a time) with
        ingested_via='import'. Capped to MAX_IMPORT_BATCH per call.

        Idempotent + resumable: each session is persisted independently and
        deduped on (user_id, fingerprint). A failed/interrupted call (e.g. a
        process stop mid-import) can be safely RESUBMITTED by the agent — the
        already-scored sessions are skipped and only the rest are scored.
        """
        total = len(packets)
        if total > MAX_IMPORT_BATCH:
            logger.info(
                "[AURA-SCORING] import_sessions truncated: %d packets -> first %d "
                "(user=%s)",
                total, MAX_IMPORT_BATCH, user_id,
            )
            packets = packets[:MAX_IMPORT_BATCH]

        existing = self._existing_fingerprints(user_id)

        # Dedup up front (and guard in-batch dupes) -> the set we actually score.
        todo: List[tuple[str, EvidencePacket]] = []
        skipped = 0
        for packet in packets:
            fingerprint = session_fingerprint(packet)
            if fingerprint in existing:
                skipped += 1
                continue
            existing.add(fingerprint)
            todo.append((fingerprint, packet))

        if not todo:
            logger.info(
                "[AURA-SCORING] import_sessions: nothing new (%d skipped) for user=%s",
                skipped, user_id,
            )
            return []

        sem = asyncio.Semaphore(IMPORT_CONCURRENCY)

        async def _score_guarded(fingerprint: str, packet: EvidencePacket):
            # One bad/slow packet must never abort the whole batch.
            async with sem:
                try:
                    return await self._score_one(
                        user_id=user_id,
                        evidence=packet,
                        fingerprint=fingerprint,
                        ingested_via="import",
                    )
                except Exception as exc:
                    logger.error(
                        "[AURA-SCORING] import_sessions: packet %s failed: %s",
                        fingerprint, exc,
                    )
                    return None

        logger.info(
            "[AURA-SCORING] import_sessions: scoring %d new session(s) at "
            "concurrency=%d (%d skipped) for user=%s",
            len(todo), IMPORT_CONCURRENCY, skipped, user_id,
        )
        gathered = await asyncio.gather(
            *(_score_guarded(fp, p) for fp, p in todo)
        )
        results: List[ScoreResult] = [r for r in gathered if r is not None]

        logger.info(
            "[AURA-SCORING] import_sessions done: %d scored, %d skipped "
            "(already imported) for user=%s",
            len(results), skipped, user_id,
        )
        return results

    # -- core scoring -------------------------------------------------------

    async def _score_one(
        self,
        user_id: str,
        evidence: EvidencePacket,
        fingerprint: str,
        ingested_via: str,
    ) -> ScoreResult:
        """Score a single packet and persist it. Robust to LLM/parse failure."""
        # 1. Modality — classify if the packet didn't declare one.
        modality = evidence.modality or self._safe_classify(evidence)
        model = _model_module(modality)
        model_version = model.get_model_version()

        logger.debug(
            "[AURA-SCORING] Scoring session fp=%s user=%s modality=%s source=%s "
            "model=%s scoring_model_version=%s",
            fingerprint, user_id, modality, evidence.source,
            AURA_SCORING_MODEL, model_version,
        )

        active_dims = model.get_active_dimensions("mvp")
        weights = model.get_dimension_weights(active_dims)

        # 2. Engagement level (derived from transcript substance) — drives caps.
        engagement_level = self._compute_engagement_level(evidence)
        logger.debug("[AURA-SCORING] Engagement level: %s", engagement_level)

        # 3. Build the referenceless prompt + call the LLM (reused client).
        prompt = self._build_scoring_prompt(
            evidence, active_dims, modality, model.AURA_PROMPT_FRAMING
        )
        logger.debug("[AURA-SCORING] Prompt built (%d chars)", len(prompt))

        llm_response = await self._call_llm(prompt)
        if not llm_response or "dimensions" not in llm_response:
            logger.error(
                "[AURA-SCORING] LLM returned no usable response for fp=%s — "
                "marking scoring_failed", fingerprint,
            )
            return self._failed_result(
                user_id, evidence, fingerprint, modality, model_version,
                ingested_via,
            )

        try:
            return self._finalize(
                user_id=user_id,
                evidence=evidence,
                fingerprint=fingerprint,
                modality=modality,
                model=model,
                model_version=model_version,
                active_dims=active_dims,
                weights=weights,
                engagement_level=engagement_level,
                llm_response=llm_response,
                ingested_via=ingested_via,
            )
        except Exception as exc:
            logger.error(
                "[AURA-SCORING] Post-LLM finalize failed for fp=%s: %s",
                fingerprint, exc,
            )
            import traceback
            logger.error("[AURA-SCORING] Traceback: %s", traceback.format_exc())
            return self._failed_result(
                user_id, evidence, fingerprint, modality, model_version,
                ingested_via,
            )

    def _finalize(
        self,
        user_id: str,
        evidence: EvidencePacket,
        fingerprint: str,
        modality: str,
        model,
        model_version: str,
        active_dims: Dict[str, Any],
        weights: Dict[str, float],
        engagement_level: str,
        llm_response: Dict[str, Any],
        ingested_via: str,
    ) -> ScoreResult:
        """Turn a parsed LLM response into a persisted ScoreResult."""
        raw_dims = llm_response.get("dimensions", {})

        # 4. Normalise per-dimension scores + reasoning (clamped 0-10).
        dimension_scores: Dict[str, DimensionScore] = {}
        for dim_key in active_dims:
            dim_data = raw_dims.get(dim_key, {}) if isinstance(raw_dims, dict) else {}
            score = self._clamp(dim_data.get("score", 0.0))
            reasoning = str(dim_data.get("reasoning", "") or dim_data.get("justification", ""))
            dimension_scores[dim_key] = {"score": score, "reasoning": reasoning}

        # 5. Engagement dampening — cap craft/output dims when substance is thin.
        self._apply_dampening(dimension_scores, engagement_level, model)

        # 6. Weighted overall (post-dampening) + Aura band label.
        overall = 0.0
        for dim_key, weight in weights.items():
            overall += dimension_scores.get(dim_key, {}).get("score", 0.0) * weight
        overall = round(overall, 2)
        aura_level = model.get_aura_label(overall)
        logger.debug(
            "[AURA-SCORING] Overall: %s (%s) for fp=%s", overall, aura_level, fingerprint,
        )

        # 7. Human-contribution meta-label (unweighted dimension).
        hc_score = dimension_scores.get("human_contribution", {}).get("score", 0.0)
        hc_label = model.get_human_contribution_label(hc_score)

        # 8. Cards — telemetry/score cards from the signal extractor + the
        #    LLM's qualitative cards (go_to_phrase / signature / growth_edge).
        telemetry = self._build_telemetry(evidence)
        llm_cards = self._extract_llm_cards(llm_response, modality)
        # Lifecycle stages the scoring LLM detected (robust to phrasing). Unioned
        # with the deterministic floor inside build_session_cards for the
        # "Ships it" card; tolerate a missing/oddly-typed field.
        llm_lifecycle = llm_response.get("lifecycle_stages")
        if not isinstance(llm_lifecycle, list):
            llm_lifecycle = None
        try:
            base_cards = build_session_cards(
                evidence, dimension_scores, modality, llm_lifecycle=llm_lifecycle
            ) or []
        except Exception as exc:
            logger.warning("[AURA-SCORING] build_session_cards failed: %s", exc)
            base_cards = []
        cards: List[Card] = list(base_cards) + llm_cards

        # 9. Archetype (from dimensions + telemetry + modality).
        try:
            archetype = assign_archetype(dimension_scores, telemetry, modality)
        except Exception as exc:
            logger.warning("[AURA-SCORING] assign_archetype failed: %s", exc)
            archetype = ""

        # 10. Profile delta vs the user's prior average aura_score.
        prior_avg = self._prior_avg_score(user_id, exclude_fingerprint=fingerprint)
        profile_delta = self._profile_delta(overall, prior_avg)

        # 11. Persist (upsert on (user_id, fingerprint)).
        session_id = self._persist_session(
            user_id=user_id,
            fingerprint=fingerprint,
            evidence=evidence,
            modality=modality,
            aura_score=overall,
            aura_level=aura_level,
            archetype=archetype,
            dimension_scores=dimension_scores,
            cards=cards,
            human_contribution_label=hc_label,
            engagement_level=engagement_level,
            model_version=model_version,
            telemetry=telemetry,
            ingested_via=ingested_via,
            status="scored",
        )

        result: ScoreResult = {
            "session_id": session_id,
            "aura_score": overall,
            "aura_level": aura_level,
            "archetype": archetype,
            "dimension_scores": dimension_scores,
            "cards": cards,
            "human_contribution_label": hc_label,
            "model_version": model_version,
            "profile_delta": profile_delta,
            # Always present so the MCP structured-output schema (array) validates;
            # score_evidence overwrites it with real PFG check-tips when grounding
            # runs against a configured graph.
            "pfg_check_tips": [],
        }
        logger.info(
            "[AURA-SCORING] Done fp=%s -> session_id=%s score=%s level=%s "
            "archetype=%s delta=%s",
            fingerprint, session_id, overall, aura_level, archetype,
            profile_delta.get("delta"),
        )
        return result

    # -- modality / engagement ---------------------------------------------

    def _safe_classify(self, evidence: EvidencePacket) -> str:
        try:
            modality = classify_modality(evidence)
            return modality if modality in ("coding", "noncoding") else "coding"
        except Exception as exc:
            logger.warning(
                "[AURA-SCORING] classify_modality failed (%s) — defaulting to coding",
                exc,
            )
            return "coding"

    def _compute_engagement_level(self, evidence: EvidencePacket) -> str:
        """Derive engagement from a COMPOSITE of behavioral signals.

        Engagement gates the craft-dimension dampening. It must reflect how much
        the human actually DROVE the session — not just the human/total token
        ratio (which is wrong or zero when the source reports no tokens). So we
        combine source-independent signals:
          - number of USER turns (did the human drive the session?)
          - USER token volume (depth of the human's input)
          - tool-call count & diversity + subagent count (measured local_stats):
            heavy orchestration is strong evidence the human was steering, even
            with few/terse prompts — so it lifts engagement and prevents an
            unfair cap on a genuinely hands-on session.

        Returns one of 'low' | 'moderate' | 'high' (matches the dampening keys
        in the model's engagement_thresholds). Token *share* never gates this —
        missing/estimated telemetry is never a penalty.
        """
        user_turns = [t for t in evidence.turns if t.role == "user"]
        n_user = len(user_turns)

        user_tokens = 0
        for t in user_turns:
            if t.token_est:
                user_tokens += int(t.token_est)
            else:
                # ~4 chars/token heuristic on the redacted excerpt.
                user_tokens += max(1, len(t.text_excerpt or "") // 4)

        # Tool / agent orchestration — measured behavioral activity.
        stats = evidence.local_stats or {}
        tools = stats.get("tools_used")
        if isinstance(tools, dict):
            n_tool_calls = sum(int(v) for v in tools.values() if isinstance(v, (int, float)))
            n_distinct_tools = len(tools)
        else:
            n_tool_calls = n_distinct_tools = 0
        n_subagents = stats.get("subagent_count")
        n_subagents = int(n_subagents) if isinstance(n_subagents, (int, float)) else 0

        score = 0
        # User turn count: 0-2 -> 0, 3-7 -> 1, 8+ -> 2
        if n_user >= 8:
            score += 2
        elif n_user >= 3:
            score += 1
        # User token volume: <150 -> 0, 150-600 -> 1, 600+ -> 2
        if user_tokens >= 600:
            score += 2
        elif user_tokens >= 150:
            score += 1
        # Tool / agent activity: heavy orchestration -> +2, some -> +1.
        if n_tool_calls >= 10 or n_distinct_tools >= 3 or n_subagents >= 1:
            score += 2
        elif n_tool_calls >= 3:
            score += 1

        if score <= 1:
            return "low"
        if score <= 2:
            return "moderate"
        return "high"

    def _apply_dampening(
        self,
        dimension_scores: Dict[str, DimensionScore],
        engagement_level: str,
        model,
    ) -> bool:
        """Cap output/craft dimension scores when engagement is low.

        Server-side enforcement against the Aura model's dampening_rules.
        Process dims (prompting, ai_pairing) are not capped.
        """
        rules = model.get_dampening_rules()
        thresholds = rules.get("engagement_thresholds", {})
        config = thresholds.get(engagement_level.lower())
        if not config:
            return False

        max_score = config.get("max_output_score", 10.0)
        output_dims = rules.get("output_quality_dimensions", [])
        capped = False
        for dim_key in output_dims:
            dim = dimension_scores.get(dim_key)
            if not dim:
                continue
            current = dim.get("score", 0.0)
            if current > max_score:
                logger.debug(
                    "[AURA-SCORING] Dampening %s: %s -> %s (engagement=%s)",
                    dim_key, current, max_score, engagement_level,
                )
                dim["score"] = max_score
                note = (
                    f" [Capped from {current} to {max_score}: {engagement_level} "
                    "engagement — thin transcript substance cannot credibly "
                    "support a high craft score.]"
                )
                dim["reasoning"] = (dim.get("reasoning", "") or "") + note
                capped = True
        return capped

    # -- prompt building ----------------------------------------------------

    def _build_scoring_prompt(
        self,
        evidence: EvidencePacket,
        active_dims: Dict[str, Any],
        modality: str,
        framing: str,
    ) -> str:
        """Build the referenceless scoring prompt.

        Sections: framing (no-rubric guardrail) -> session meta -> transcript
        excerpts -> files-touched summary -> dimension definitions -> the
        JSON response contract (dimension scores + reasoning + qualitative cards).
        """
        parts: List[str] = [
            "You are the scoring engine for VibeLevel Aura.",
            "",
            "## FRAMING",
            framing,
            "",
            "## SESSION METADATA",
            f"- Source: {evidence.source}",
            f"- Modality: {modality}",
        ]
        if evidence.title:
            parts.append(f"- Title: {evidence.title}")
        if evidence.model:
            parts.append(f"- AI model used: {evidence.model}")
        if evidence.started_at:
            parts.append(f"- Started: {evidence.started_at}")
        if evidence.ended_at:
            parts.append(f"- Ended: {evidence.ended_at}")

        # --- Transcript excerpts ---
        parts.append("")
        parts.append("## TRANSCRIPT EXCERPTS (chronological; redacted/truncated)")
        turns = evidence.turns[-MAX_TURNS:]
        if len(evidence.turns) > MAX_TURNS:
            parts.append(
                f"(Showing the last {MAX_TURNS} of {len(evidence.turns)} turns.)"
            )
        if turns:
            for t in turns:
                role = t.role.upper()
                excerpt = (t.text_excerpt or "").strip()
                if len(excerpt) > MAX_EXCERPT_CHARS:
                    excerpt = excerpt[:MAX_EXCERPT_CHARS] + " …[truncated]"
                tool = f" (tool: {t.tool_name})" if t.tool_name else ""
                parts.append(f"**[{role}{tool}]:** {excerpt}")
                parts.append("")
        else:
            parts.append("No transcript turns were captured for this session.")

        # --- Files touched summary (digests only; no contents) ---
        parts.append("")
        parts.append("## FILES TOUCHED (summary only — no file contents)")
        files = evidence.files_touched[:MAX_FILES]
        if files:
            for f in files:
                bits = [f.path]
                if f.lang:
                    bits.append(f"lang={f.lang}")
                if f.ops:
                    bits.append(f"op={f.ops}")
                if f.bytes is not None:
                    bits.append(f"bytes={f.bytes}")
                parts.append(f"- {'  '.join(bits)}")
            if len(evidence.files_touched) > MAX_FILES:
                parts.append(
                    f"- …and {len(evidence.files_touched) - MAX_FILES} more file(s)."
                )
        else:
            parts.append("No file activity was recorded for this session.")

        # --- Dimensions ---
        parts.append("")
        parts.append("## SCORING DIMENSIONS")
        parts.append(
            "Score EACH dimension 0.0-10.0 against its sub-criteria, judging ONLY "
            "the human's process/collaboration as evidenced above. Give a 1-2 "
            "sentence reasoning per dimension citing specific evidence."
        )
        for i, (key, dim) in enumerate(active_dims.items(), 1):
            parts.append("")
            parts.append(f"### {i}. {dim['name']}  (key: `{key}`)")
            parts.append(dim.get("description", ""))
            sub = dim.get("sub_criteria", [])
            if sub:
                parts.append("Sub-criteria:")
                for crit in sub:
                    parts.append(f"  - {crit}")

        # --- Lifecycle (spec follow-up: did the work go end-to-end?) ---
        if modality == MODALITY_CODING:
            life_stages = ["build", "test", "deploy", "verify", "ci", "infra"]
            life_desc = (
                "build = wrote/changed code; test = ran tests/compiles; deploy = "
                "shipped (fly/vercel/docker/k8s/etc.); verify = checked logs/health/"
                "output after; ci = CI/workflow config; infra = IaC/containers."
            )
            life_credit = "Verification and Product Thinking"
        else:
            life_stages = ["research", "outline", "revise", "fact_check", "deliver"]
            life_desc = (
                "research = gathered sources/data; outline = structured before "
                "drafting; revise = edited/rewrote/iterated; fact_check = verified "
                "claims/citations; deliver = produced/finalized a real deliverable "
                "(a document created/exported, a piece published)."
            )
            life_credit = "Deliverable Quality, Verification and Structured Thinking"
        parts.append("")
        parts.append("## LIFECYCLE")
        parts.append(
            "Identify which lifecycle stages the transcript ACTUALLY evidences "
            f"(choose from: {', '.join(life_stages)}). {life_desc}"
        )
        parts.append(
            "Return them in `lifecycle_stages`. Taking the work through its "
            f"lifecycle is a strength: when stages are genuinely present, credit {life_credit} "
            "accordingly. Do NOT list a stage that is not evidenced, and do NOT add a "
            "flat bonus — only let real lifecycle evidence raise those dimensions."
        )

        # --- Response contract ---
        dim_example = {k: {"score": 0.0, "reasoning": "..."} for k in active_dims}
        response_schema = {
            "dimensions": dim_example,
            "lifecycle_stages": life_stages[:2] + ["..."],
            "cards": {
                "go_to_phrase": "the human's most characteristic/most-used prompt phrase, verbatim and short",
                "signature": "one short sentence naming this person's signature working move",
                "growth_edge": "one short sentence naming the single biggest thing they could improve",
            },
        }
        parts.append("")
        parts.append("## RESPONSE FORMAT")
        parts.append("Respond with ONLY valid JSON matching this exact structure:")
        parts.append(f"```json\n{json.dumps(response_schema, indent=2)}\n```")
        parts.append("")
        parts.append("RULES:")
        parts.append("- Every dimension score is a float in [0.0, 10.0].")
        parts.append("- `reasoning` cites specific transcript/file evidence (1-2 sentences).")
        parts.append("- `cards.go_to_phrase` must be a short verbatim phrase from the human's own messages.")
        parts.append("- `lifecycle_stages` lists ONLY stages with explicit evidence (may be empty).")
        parts.append("- Where evidence is thin, score conservatively and say so in the reasoning.")
        parts.append("- Output ONLY the JSON object, no prose before or after.")

        return "\n".join(parts)

    # -- LLM call (same client, off-thread, fence-parse) --

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call the scoring LLM and parse its JSON. Retries up to 3 times.

        Reuses `model_config_manager.create_llm` + LangChain `HumanMessage`,
        invoked via `asyncio.to_thread`.
        """
        from ...core.model_config import model_config_manager
        from langchain_core.messages import HumanMessage

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(
                    "[AURA-SCORING] Calling LLM (attempt %d/%d, model=%s)",
                    attempt, max_attempts, AURA_SCORING_MODEL,
                )
                llm = model_config_manager.create_llm(
                    AURA_SCORING_MODEL,
                    temperature=0.3,
                    max_tokens=8192,
                    streaming=False,
                )
                response = await asyncio.to_thread(
                    llm.invoke, [HumanMessage(content=prompt)]
                )
                text = response.content if isinstance(response.content, str) else str(response.content)
                logger.debug("[AURA-SCORING] LLM response received (%d chars)", len(text))

                if not text.strip():
                    logger.warning("[AURA-SCORING] Empty LLM response (attempt %d)", attempt)
                    if attempt < max_attempts:
                        await asyncio.sleep(2)
                        continue
                    return None

                json_text = text.strip()
                if "```json" in json_text:
                    json_text = json_text.split("```json", 1)[1].split("```", 1)[0]
                elif "```" in json_text:
                    json_text = json_text.split("```", 1)[1].split("```", 1)[0]

                result = json.loads(json_text.strip())
                if "dimensions" not in result:
                    logger.warning(
                        "[AURA-SCORING] Response missing 'dimensions' (attempt %d)", attempt,
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(2)
                        continue
                    return None

                # Clamp dimension scores up-front (defensive).
                for dim_data in result.get("dimensions", {}).values():
                    if isinstance(dim_data, dict) and "score" in dim_data:
                        dim_data["score"] = self._clamp(dim_data["score"])
                return result

            except json.JSONDecodeError as exc:
                logger.warning("[AURA-SCORING] JSON parse error (attempt %d): %s", attempt, exc)
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                    continue
                return None
            except Exception as exc:
                logger.error("[AURA-SCORING] LLM call error (attempt %d): %s", attempt, exc)
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                    continue
                return None

        return None

    # -- card / telemetry helpers ------------------------------------------

    def _extract_llm_cards(
        self, llm_response: Dict[str, Any], modality: str
    ) -> List[Card]:
        """Turn the LLM's `cards` object into Card dicts per the model taxonomy."""
        raw = llm_response.get("cards", {})
        if not isinstance(raw, dict):
            return []

        # id -> (klass, question, headline) — mirrors aura_model_coding.card_signals
        spec = {
            "go_to_phrase": ("personality", "What's your go-to prompt?", "Go-to phrase"),
            "signature": ("personality", "Your signature move?", "Signature move"),
            "growth_edge": ("credibility", "Your growth edge?", "Growth edge"),
        }
        cards: List[Card] = []
        for card_id, (klass, question, headline) in spec.items():
            value = raw.get(card_id)
            if value is None:
                continue
            detail = str(value).strip()
            if not detail:
                continue
            cards.append({
                "id": card_id,
                "scope": "session",
                "klass": klass,
                "modality": modality,
                "question": question,
                "headline": headline,
                "detail": detail,
                "stat": detail,
            })
        return cards

    def _build_telemetry(self, evidence: EvidencePacket) -> Dict[str, Any]:
        """Cheap, deterministic per-session telemetry passed to assign_archetype.

        The signal extractor owns the rich telemetry/card derivation; here we
        just supply a compact, self-contained snapshot from the packet so the
        archetype assigner has signals to work with even in isolation.
        """
        turns = evidence.turns
        user_turns = [t for t in turns if t.role == "user"]
        return {
            "turn_count": len(turns),
            "user_turn_count": len(user_turns),
            "tool_turn_count": sum(1 for t in turns if t.role == "tool"),
            "files_touched": len(evidence.files_touched),
            "source": evidence.source,
            "local_stats": evidence.local_stats or {},
        }

    # -- persistence --------------------------------------------------------

    def _persist_session(
        self,
        user_id: str,
        fingerprint: str,
        evidence: EvidencePacket,
        modality: str,
        aura_score: float,
        aura_level: str,
        archetype: str,
        dimension_scores: Dict[str, DimensionScore],
        cards: List[Card],
        human_contribution_label: str,
        engagement_level: str,
        model_version: str,
        telemetry: Dict[str, Any],
        ingested_via: str,
        status: str,
    ) -> str:
        """Upsert the AuraSession row on (user_id, fingerprint). Returns its id."""
        pool = get_pool()
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO "AuraSession" (
                        user_id, fingerprint, source, modality, title, evidence,
                        aura_score, aura_level, archetype,
                        dimension_scores, cards, human_contribution_label,
                        engagement_level, model_version, telemetry,
                        ingested_via, status, started_at, ended_at,
                        created_at, updated_at
                    ) VALUES (
                        %(user_id)s, %(fingerprint)s, %(source)s, %(modality)s, %(title)s, %(evidence)s,
                        %(aura_score)s, %(aura_level)s, %(archetype)s,
                        %(dimension_scores)s, %(cards)s, %(human_contribution_label)s,
                        %(engagement_level)s, %(model_version)s, %(telemetry)s,
                        %(ingested_via)s, %(status)s, %(started_at)s, %(ended_at)s,
                        %(now)s, %(now)s
                    )
                    ON CONFLICT (user_id, fingerprint) DO UPDATE SET
                        source = EXCLUDED.source,
                        modality = EXCLUDED.modality,
                        title = EXCLUDED.title,
                        evidence = EXCLUDED.evidence,
                        aura_score = EXCLUDED.aura_score,
                        aura_level = EXCLUDED.aura_level,
                        archetype = EXCLUDED.archetype,
                        dimension_scores = EXCLUDED.dimension_scores,
                        cards = EXCLUDED.cards,
                        human_contribution_label = EXCLUDED.human_contribution_label,
                        engagement_level = EXCLUDED.engagement_level,
                        model_version = EXCLUDED.model_version,
                        telemetry = EXCLUDED.telemetry,
                        ingested_via = EXCLUDED.ingested_via,
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        ended_at = EXCLUDED.ended_at,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                    """,
                    {
                        "user_id": user_id,
                        "fingerprint": fingerprint,
                        "source": evidence.source,
                        "modality": modality,
                        "title": evidence.title,
                        "evidence": json.dumps(evidence.model_dump(mode="json")),
                        "aura_score": aura_score,
                        "aura_level": aura_level,
                        "archetype": archetype,
                        "dimension_scores": json.dumps(dimension_scores),
                        "cards": json.dumps(cards),
                        "human_contribution_label": human_contribution_label,
                        "engagement_level": engagement_level,
                        "model_version": model_version,
                        "telemetry": json.dumps(telemetry),
                        "ingested_via": ingested_via,
                        "status": status,
                        "started_at": evidence.started_at,
                        "ended_at": evidence.ended_at,
                        "now": datetime.utcnow(),
                    },
                )
                row = cur.fetchone()
                conn.commit()
                session_id = str(row["id"]) if row else ""
                logger.debug(
                    "[AURA-SCORING] Persisted AuraSession id=%s fp=%s (status=%s)",
                    session_id, fingerprint, status,
                )
                return session_id
        except Exception as exc:
            logger.error("[AURA-SCORING] Error persisting AuraSession fp=%s: %s", fingerprint, exc)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.putconn(conn)

    def _existing_fingerprints(self, user_id: str) -> set:
        """All fingerprints already scored for a user (for import dedup)."""
        pool = get_pool()
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT fingerprint FROM "AuraSession" WHERE user_id = %s',
                    (user_id,),
                )
                return {r[0] for r in cur.fetchall()}
        except Exception as exc:
            logger.warning(
                "[AURA-SCORING] Could not load existing fingerprints for user=%s: %s",
                user_id, exc,
            )
            return set()
        finally:
            if conn:
                pool.putconn(conn)

    def _prior_avg_score(
        self, user_id: str, exclude_fingerprint: str
    ) -> Optional[float]:
        """Average aura_score of the user's prior *scored* sessions.

        Excludes the current fingerprint so a re-score (upsert) compares against
        the rest of the profile, not against its own previous value.
        """
        pool = get_pool()
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT AVG(aura_score)
                    FROM "AuraSession"
                    WHERE user_id = %s
                      AND fingerprint <> %s
                      AND status = 'scored'
                    """,
                    (user_id, exclude_fingerprint),
                )
                row = cur.fetchone()
                if row and row[0] is not None:
                    return float(row[0])
                return None
        except Exception as exc:
            logger.warning(
                "[AURA-SCORING] Could not compute prior avg for user=%s: %s",
                user_id, exc,
            )
            return None
        finally:
            if conn:
                pool.putconn(conn)

    # -- small pure helpers -------------------------------------------------

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return max(0.0, min(10.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _profile_delta(
        overall: float, prior_avg: Optional[float]
    ) -> Dict[str, Any]:
        """Change of this session's overall vs the user's running profile avg."""
        if prior_avg is None:
            return {
                "delta": None,
                "prior_avg": None,
                "new_score": overall,
                "is_first_session": True,
            }
        delta = round(overall - prior_avg, 2)
        return {
            "delta": delta,
            "prior_avg": round(prior_avg, 2),
            "new_score": overall,
            "is_first_session": False,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        }

    def _failed_result(
        self,
        user_id: str,
        evidence: EvidencePacket,
        fingerprint: str,
        modality: str,
        model_version: str,
        ingested_via: str,
    ) -> ScoreResult:
        """Persist a minimal scoring_failed row and return a minimal ScoreResult."""
        session_id = ""
        try:
            session_id = self._persist_session(
                user_id=user_id,
                fingerprint=fingerprint,
                evidence=evidence,
                modality=modality,
                aura_score=0.0,
                aura_level="",
                archetype="",
                dimension_scores={},
                cards=[],
                human_contribution_label="",
                engagement_level="",
                model_version=model_version,
                telemetry=self._build_telemetry(evidence),
                ingested_via=ingested_via,
                status="scoring_failed",
            )
        except Exception as exc:
            logger.error(
                "[AURA-SCORING] Could not persist scoring_failed row for fp=%s: %s",
                fingerprint, exc,
            )
        return {
            "session_id": session_id,
            "aura_score": 0.0,
            "aura_level": "",
            "archetype": "",
            "dimension_scores": {},
            "cards": [],
            "human_contribution_label": "",
            "model_version": model_version,
            "profile_delta": {"delta": None, "prior_avg": None, "new_score": 0.0,
                              "is_first_session": False, "status": "scoring_failed"},
            "pfg_check_tips": [],
        }


# ---------------------------------------------------------------------------
# Module-level cached singleton
# ---------------------------------------------------------------------------

_scorer_singleton: Optional[AuraScoringService] = None


def get_aura_scorer() -> AuraScoringService:
    """Return the process-wide cached AuraScoringService singleton."""
    global _scorer_singleton
    if _scorer_singleton is None:
        _scorer_singleton = AuraScoringService()
    return _scorer_singleton
