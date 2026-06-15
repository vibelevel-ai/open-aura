"""VibeLevel Aura — standalone scoring for real, self-directed AI work sessions.

This package is fully independent of the assessment/Hiring scoring engine
(`scoring_service_v2/v3`). It has its own model definitions, scoring pipeline,
signal extractor, and persistence (`aura_session`). It reuses only platform
infra (DB pool, LLM client, auth) — never assessment scoring logic.

See docs/AI_WORK_PROFILE_CONNECTOR_POC.md (decision #17).
"""
