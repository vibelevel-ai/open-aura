from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.services.aura.aura_profile_facts import (
    aggregate_profile_facts,
    normalize_inferred_profile_facts,
    sanitize_mcp_name,
    sanitize_repository_name,
    sanitize_summary,
)


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def row(
    *,
    created_at: str,
    aura_score: float = 8.0,
    source: str = "codex",
    model: str = "gpt-5",
    facts: dict | None = None,
    tools: dict | None = None,
    skills: list[str] | None = None,
    mcp_servers: list[str] | None = None,
    repository: str | None = None,
    project_summary: str | None = None,
) -> dict:
    local_stats: dict = {}
    if tools is not None:
        local_stats["tools_used"] = tools
    if skills is not None:
        local_stats["skills_used"] = skills
    workspace_context: dict = {}
    if mcp_servers is not None:
        workspace_context["mcp_servers"] = mcp_servers
    if repository is not None:
        workspace_context["repository"] = repository
    if project_summary is not None:
        workspace_context["project_summary"] = project_summary
    return {
        "created_at": created_at,
        "aura_score": aura_score,
        "source": source,
        "telemetry": {"profile_facts": facts or {}},
        "evidence": {
            "source": source,
            "model": model,
            "local_stats": local_stats,
            "workspace_context": workspace_context,
        },
    }


def fact(value: str, confidence: float, source: str = "inferred") -> dict:
    return {
        "value": value,
        "confidence": confidence,
        "source": source,
        "evidence": "redacted session evidence",
    }


class SanitizationTests(unittest.TestCase):
    def test_repository_sanitization_keeps_only_project_name(self) -> None:
        self.assertEqual(
            sanitize_repository_name("git@github.com:vibelevel-ai/open-aura.git"),
            "open-aura",
        )
        self.assertEqual(
            sanitize_repository_name("/home/person/work/private/open-aura"),
            "open-aura",
        )

    def test_mcp_sanitization_rejects_urls_and_secret_like_values(self) -> None:
        self.assertEqual(sanitize_mcp_name("GitHub"), "GitHub")
        self.assertIsNone(sanitize_mcp_name("https://user:token@internal.example/mcp"))
        self.assertIsNone(sanitize_mcp_name("api_key=super-secret"))

    def test_summary_sanitization_rejects_secret_like_values(self) -> None:
        self.assertEqual(
            sanitize_summary("  Local AI session scoring and profile viewer.  "),
            "Local AI session scoring and profile viewer.",
        )
        self.assertIsNone(sanitize_summary("API_KEY=do-not-store"))

    def test_inferred_facts_are_typed_bounded_and_secret_free(self) -> None:
        normalized = normalize_inferred_profile_facts(
            {
                "headline": {
                    "value": "AI-native backend engineer",
                    "confidence": 1.8,
                    "evidence": "Repeated architecture and API work.",
                },
                "location": {
                    "value": "api_key=private",
                    "confidence": 0.9,
                    "evidence": "must be rejected",
                },
                "unknown_key": {"value": "ignored", "confidence": 1},
            }
        )
        self.assertEqual(normalized["headline"]["confidence"], 1.0)
        self.assertEqual(normalized["headline"]["source"], "inferred")
        self.assertNotIn("location", normalized)
        self.assertNotIn("unknown_key", normalized)


class AggregationTests(unittest.TestCase):
    def test_empty_and_legacy_rows_are_safe(self) -> None:
        self.assertEqual(
            aggregate_profile_facts([], now=NOW),
            {"profile_facts": {}, "toolkit": {}, "projects": []},
        )
        result = aggregate_profile_facts(
            [{"created_at": "broken", "evidence": None, "telemetry": None}],
            now=NOW,
        )
        self.assertEqual(result["profile_facts"], {})
        self.assertEqual(result["projects"], [])

    def test_repeated_evidence_beats_one_unusual_session(self) -> None:
        rows = [
            row(
                created_at="2026-07-25T09:00:00Z",
                facts={"headline": fact("Backend specialist", 0.95)},
            ),
            row(
                created_at="2026-07-24T09:00:00Z",
                facts={"headline": fact("AI-native full-stack builder", 0.72)},
            ),
            row(
                created_at="2026-07-23T09:00:00Z",
                facts={"headline": fact("AI-native full-stack builder", 0.72)},
            ),
        ]
        result = aggregate_profile_facts(rows, now=NOW)
        self.assertEqual(
            result["profile_facts"]["headline"]["value"],
            "AI-native full-stack builder",
        )
        self.assertEqual(result["profile_facts"]["headline"]["observations"], 2)

    def test_measured_fact_outweighs_equal_inferred_fact(self) -> None:
        rows = [
            row(
                created_at="2026-07-25T09:00:00Z",
                facts={"location": fact("Remote", 0.8, "measured")},
            ),
            row(
                created_at="2026-07-25T08:00:00Z",
                facts={"location": fact("London", 0.8, "inferred")},
            ),
        ]
        result = aggregate_profile_facts(rows, now=NOW)
        self.assertEqual(result["profile_facts"]["location"]["value"], "Remote")

    def test_equal_weight_values_use_locale_independent_lexical_order(self) -> None:
        rows = [
            row(
                created_at="2026-07-25T09:00:00Z",
                facts={"availability": fact("Open to work", 0.8)},
            ),
            row(
                created_at="2026-07-25T09:00:00Z",
                facts={"availability": fact("Interviewing", 0.8)},
            ),
        ]
        result = aggregate_profile_facts(rows, now=NOW)
        self.assertEqual(
            result["profile_facts"]["availability"]["value"],
            "Interviewing",
        )

    def test_toolkit_aggregates_measured_session_metadata(self) -> None:
        rows = [
            row(
                created_at="2026-07-25T09:00:00Z",
                source="codex",
                model="gpt-5",
                tools={"Read": 4, "Edit": 2},
                skills=["code-review", "  "],
                mcp_servers=["GitHub", "https://token@example.test/mcp"],
            ),
            row(
                created_at="2026-07-24T09:00:00Z",
                source="claude_code",
                model="claude-opus",
                tools={"Read": 3},
                skills=["code-review", "research"],
                mcp_servers=["GitHub", "Context7"],
            ),
        ]
        toolkit = aggregate_profile_facts(rows, now=NOW)["toolkit"]
        self.assertEqual(toolkit["sources"], {"claude_code": 1, "codex": 1})
        self.assertEqual(toolkit["models"], {"claude-opus": 1, "gpt-5": 1})
        self.assertEqual(toolkit["tools"][0], {"name": "Read", "count": 7})
        self.assertEqual(toolkit["skills"][0], {"name": "code-review", "count": 2})
        self.assertEqual(
            toolkit["mcp_servers"],
            [
                {"name": "GitHub", "count": 2},
                {"name": "Context7", "count": 1},
            ],
        )

    def test_projects_group_repository_evidence_and_average_aura(self) -> None:
        rows = [
            row(
                created_at="2026-07-25T09:00:00Z",
                repository="git@github.com:vibelevel-ai/open-aura.git",
                project_summary="Local AI session scoring.",
                aura_score=8.4,
            ),
            row(
                created_at="2026-07-24T09:00:00Z",
                repository="/work/open-aura",
                project_summary="Local profile viewer.",
                aura_score=7.6,
            ),
        ]
        projects = aggregate_profile_facts(rows, now=NOW)["projects"]
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "open-aura")
        self.assertEqual(projects[0]["session_count"], 2)
        self.assertEqual(projects[0]["aura_score"], 8.0)
        self.assertNotIn("/work", str(projects[0]))


if __name__ == "__main__":
    unittest.main()
