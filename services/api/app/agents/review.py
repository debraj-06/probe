"""Review AI — validation, deduplication, correlation and reporting.

The interesting part of PROBE is not "the AI found 12 bugs". It is that several
perspectives investigated the same software and Review AI noticed they were
describing the *same underlying problem*:

    Technical AI -> payment request takes 8 seconds
    UX/UI AI     -> no useful loading feedback
    Chaos AI     -> pay can be clicked repeatedly
                     |
                  REVIEW AI
                     |
        "Potential duplicate submission under slow response"
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..db import new_id
from .base import SEVERITY_ORDER, AgentContext, Discovery
from .roles import REVIEW

logger = logging.getLogger("probe.review")

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "with", "is", "are", "was",
    "were", "be", "been", "it", "its", "this", "that", "for", "by", "at", "from", "as",
    "no", "not", "can", "could", "should", "would", "when", "what", "how", "into",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class ReviewAgent:
    """Turns raw agent discoveries into the final, deduplicated finding set."""

    role = REVIEW.role
    label = REVIEW.label

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm

    # ------------------------------------------------------------------
    async def review(self, ctx: AgentContext, discoveries: list[Discovery]) -> list[dict[str, Any]]:
        await ctx.emit(
            "review.started",
            f"Review AI received {len(discoveries)} raw discovery(ies) from "
            f"{len({a for d in discoveries for a in d.agents})} agent(s)",
            agent=self.role,
            data={"discoveries": len(discoveries)},
        )

        if not discoveries:
            await ctx.emit(
                "review.completed",
                "Review AI found nothing to validate — no findings produced.",
                agent=self.role,
                data={"findings": 0},
            )
            return []

        merged = self._deduplicate(discoveries)
        correlated = self._correlate(merged)

        for entry in correlated:
            if entry["correlated"]:
                await ctx.emit(
                    "review.correlated",
                    entry["correlation_note"],
                    agent=self.role,
                    data={
                        "agents": entry["agents"],
                        "url": entry["discoveries"][0].url,
                        "titles": [d.title for d in entry["discoveries"]],
                    },
                )

        findings: list[dict[str, Any]] = []
        for entry in correlated:
            finding = self._finalise(entry)
            findings.append(finding)
            await ctx.emit(
                "finding.created",
                f"Finding: {finding['title']} ({finding['severity']}, "
                f"{int(finding['confidence'] * 100)}% confidence)",
                agent=self.role,
                data={
                    "finding_id": finding["id"],
                    "title": finding["title"],
                    "severity": finding["severity"],
                    "category": finding["category"],
                    "confidence": finding["confidence"],
                    "agents": finding["agents"],
                    "correlated": finding["correlated"],
                },
            )

        summary = await self._summarise(ctx, findings)
        for finding in findings:
            finding.setdefault("source", {})["report_summary"] = summary

        await ctx.emit(
            "review.completed",
            f"Review AI reviewed {len(discoveries)} discovery(ies) into "
            f"{len(findings)} finding(s)",
            agent=self.role,
            data={"findings": len(findings), "summary": summary},
        )
        return findings

    # ------------------------------------------------------------------
    def _deduplicate(self, discoveries: list[Discovery]) -> list[list[Discovery]]:
        """Group discoveries that describe the same problem."""
        groups: list[list[Discovery]] = []
        for discovery in discoveries:
            placed = False
            for group in groups:
                head = group[0]
                if (
                    _similarity(head.title, discovery.title) >= 0.55
                    or (head.category == discovery.category and _similarity(head.actual, discovery.actual) >= 0.4)
                ):
                    group.append(discovery)
                    placed = True
                    break
            if not placed:
                groups.append([discovery])
        return groups

    def _correlate(self, groups: list[list[Discovery]]) -> list[dict[str, Any]]:
        """Merge groups that share a page and a symptom family."""
        merged: list[dict[str, Any]] = []
        consumed: set[int] = set()

        for index, group in enumerate(groups):
            if index in consumed:
                continue
            current = list(group)
            for other_index in range(index + 1, len(groups)):
                if other_index in consumed:
                    continue
                other = groups[other_index]
                if self._related(current, other):
                    current.extend(other)
                    consumed.add(other_index)

            agents = sorted({agent for d in current for agent in d.agents})
            if len(agents) > 1:
                ctx_sync_message = (
                    f"Related behaviour detected: {', '.join(agents)} reported "
                    f"overlapping observations on the same flow"
                )
                # emitted from the async caller via the returned marker
                merged.append(
                    {
                        "discoveries": current,
                        "agents": agents,
                        "correlated": True,
                        "correlation_note": ctx_sync_message,
                    }
                )
            else:
                merged.append(
                    {
                        "discoveries": current,
                        "agents": agents,
                        "correlated": False,
                        "correlation_note": "",
                    }
                )
        return merged

    @staticmethod
    def _related(left: list[Discovery], right: list[Discovery]) -> bool:
        """Two discoveries are related when they describe the same control.

        This is what produces PROBE's headline behaviour: several agents
        observing *different symptoms on the same control* get merged into one
        finding instead of three unrelated ones.
        """
        left_urls = {d.url for d in left if d.url}
        right_urls = {d.url for d in right if d.url}
        if not (left_urls & right_urls):
            return False

        left_targets = {d.target.lower().strip() for d in left if d.target}
        right_targets = {d.target.lower().strip() for d in right if d.target}
        if left_targets & right_targets:
            return True

        left_tags = {t for d in left for t in d.tags}
        right_tags = {t for d in right for t in d.tags}
        if left_tags & right_tags:
            return True
        return any(_similarity(d.title, e.title) >= 0.3 for d in left for e in right)

    # ------------------------------------------------------------------
    def _finalise(self, entry: dict[str, Any]) -> dict[str, Any]:
        discoveries: list[Discovery] = entry["discoveries"]
        # the most severe observation becomes the headline
        head = sorted(
            discoveries,
            key=lambda d: (SEVERITY_ORDER.get(d.severity, 3), -d.confidence),
        )[0]

        steps: list[str] = []
        for discovery in discoveries:
            for step in discovery.steps:
                if step and step not in steps:
                    steps.append(step)

        evidence: list[dict[str, Any]] = []
        for discovery in discoveries:
            for item in discovery.evidence:
                if item not in evidence:
                    evidence.append(item)

        agents = entry["agents"]
        confidence = max(d.confidence for d in discoveries)
        if len(agents) > 1:
            confidence = min(0.98, confidence + 0.05 * (len(agents) - 1))

        classification = self._classify(head, discoveries)

        # when several perspectives describe the same control, the merged
        # finding carries the contributing observations explicitly
        contributing = [
            f"{d.title} (observed by {', '.join(d.agents)})"
            for d in discoveries
            if d is not head
        ]
        description = head.description
        if contributing:
            description += (
                "\n\nContributing observations from other agents:\n"
                + "\n".join(f"• {item}" for item in contributing)
            )

        recommendations = [head.recommendation]
        for discovery in discoveries:
            if discovery is not head and discovery.recommendation not in recommendations:
                recommendations.append(discovery.recommendation)

        return {
            "id": new_id("find"),
            "inspection_id": "",
            "title": head.title,
            "category": head.category,
            "classification": classification,
            "severity": head.severity,
            "confidence": round(confidence, 2),
            "description": description,
            "expected": head.expected,
            "actual": head.actual,
            "steps": steps[:12],
            "recommendation": " ".join(r for r in recommendations if r),
            "agents": agents,
            "reproduced": self._best_reproduction(discoveries),
            "url": head.url,
            "target": head.target,
            "correlated": entry["correlated"],
            "correlation_note": entry["correlation_note"],
            "contributing_factors": contributing,
            "source": {
                "discoveries": [d.to_dict() for d in discoveries],
                "evidence": evidence,
                "correlation_note": entry["correlation_note"],
                "contributing_factors": contributing,
                "target": head.target,
                "reproductions": self._best_reproduction_count(discoveries),
                "attempts": self._best_reproduction_attempts(discoveries),
            },
        }

    @staticmethod
    def _classify(head: Discovery, discoveries: list[Discovery]) -> str:
        if head.category in {"ux", "ui", "accessibility"}:
            return "ux_issue"
        strong_evidence = any(
            e.get("kind") in {"console", "network"} for d in discoveries for e in d.evidence
        )
        reproduced = any(d.reproduced and not d.reproduced.startswith("0 /") for d in discoveries)
        if strong_evidence and reproduced:
            return "confirmed_defect"
        if reproduced and head.severity in {"critical", "high"}:
            return "confirmed_defect"
        return "improvement"

    @staticmethod
    def _best_reproduction(discoveries: list[Discovery]) -> str:
        best = "0 / 0"
        best_ratio = -1.0
        for discovery in discoveries:
            value = discovery.reproduced or ""
            match = re.match(r"(\d+)\s*/\s*(\d+)", value)
            if not match:
                continue
            got, total = int(match.group(1)), int(match.group(2))
            ratio = got / total if total else 0.0
            if ratio > best_ratio:
                best_ratio = ratio
                best = f"{got} / {total}"
        return best

    @staticmethod
    def _best_reproduction_count(discoveries: list[Discovery]) -> int:
        for discovery in discoveries:
            value = discovery.reproduced or ""
            match = re.match(r"(\d+)\s*/\s*(\d+)", value)
            if match and int(match.group(1)):
                return int(match.group(1))
        return 0

    @staticmethod
    def _best_reproduction_attempts(discoveries: list[Discovery]) -> int:
        for discovery in discoveries:
            value = discovery.reproduced or ""
            match = re.match(r"(\d+)\s*/\s*(\d+)", value)
            if match and int(match.group(2)):
                return int(match.group(2))
        return 0

    # ------------------------------------------------------------------
    async def _summarise(self, ctx: AgentContext, findings: list[dict[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for finding in findings:
            counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
        breakdown = ", ".join(
            f"{counts.get(level, 0)} {level}"
            for level in ("critical", "high", "medium", "low", "info")
        )
        correlated = [f for f in findings if f["correlated"]]
        summary = (
            f"{len(findings)} finding(s) reviewed ({breakdown}). "
            f"{len(correlated)} finding(s) were correlated across multiple agent perspectives."
        )

        if self.llm is None:
            return summary

        prompt = (
            "Write a concise executive summary using only the inspection facts below. "
            "Distinguish reproduced issues from unconfirmed observations; do not call a finding "
            "confirmed unless its reproduction count is above zero. Do not claim untested flows are "
            "defect-free or add findings that are not listed.\n\n"
            f"TARGET: {ctx.inspection['url']}\n"
            f"DEPTH: {ctx.inspection['depth']}\n"
            f"FINDINGS: {len(findings)} ({breakdown})\n\n"
            + "\n".join(
                f"- [{f['severity']}] {f['title']} "
                f"(agents: {', '.join(f['agents'])}; reproduced {f['reproduced']})"
                for f in findings[:15]
            )
        )
        try:
            text = await self.llm.complete(
                system="You are Review AI, the quality layer of an autonomous testing platform.",
                prompt=prompt,
            )
        except Exception:
            logger.exception("Review AI summary model call failed")
            raise RuntimeError("The configured review model could not complete the report.") from None
        if not text or not text.strip():
            raise RuntimeError("The configured review model returned an empty report summary.")
        return text.strip()[:1500]
