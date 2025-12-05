from __future__ import annotations

from collections.abc import Iterable

from pr_review_agent.findings.schema import Finding, Severity

REVIEW_MARKER = "<!-- pr-review-agent:run -->"

_SEVERITY_HEADERS: dict[Severity, str] = {
    Severity.CRITICAL: "Critical",
    Severity.HIGH: "High",
    Severity.MEDIUM: "Medium",
    Severity.LOW: "Low",
    Severity.INFO: "Info",
}


def compose_markdown(findings: Iterable[Finding], cost_usd: float = 0.0) -> str:
    items = list(findings)
    if not items:
        return _empty_review(cost_usd)

    ordered = sorted(items, key=lambda f: (-f.severity.rank, f.location.path, f.location.line))
    sections: list[str] = [REVIEW_MARKER, _render_tldr(ordered)]
    sections.extend(_render_severity_sections(ordered))
    sections.append(_render_footer(cost_usd, len(items)))
    return "\n\n".join(sections)


def _empty_review(cost_usd: float) -> str:
    return "\n\n".join(
        [
            REVIEW_MARKER,
            "## pr-review-agent",
            "No issues found.",
            _render_footer(cost_usd, 0),
        ]
    )


def _render_tldr(ordered: list[Finding]) -> str:
    must_read = [f for f in ordered if f.severity >= Severity.HIGH]
    if not must_read:
        n = len(ordered)
        word = "finding" if n == 1 else "findings"
        return f"## pr-review-agent\n\n{n} {word}; nothing critical or high."

    lines = ["## pr-review-agent", "", "### TL;DR"]
    for f in must_read:
        sev = _SEVERITY_HEADERS[f.severity].lower()
        loc = f"{f.location.path}:{f.location.line}"
        lines.append(f"- **{sev}** ({f.agent}): `{loc}` — {f.title}")
    return "\n".join(lines)


def _render_severity_sections(ordered: list[Finding]) -> list[str]:
    sections: list[str] = []
    by_sev: dict[Severity, list[Finding]] = {}
    for f in ordered:
        by_sev.setdefault(f.severity, []).append(f)

    for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO):
        if sev not in by_sev:
            continue
        block = [f"### {_SEVERITY_HEADERS[sev]}", ""]
        for f in by_sev[sev]:
            block.append(_render_finding(f))
            block.append("")
        sections.append("\n".join(block).rstrip() + "\n")
    return sections


def _render_finding(f: Finding) -> str:
    loc = f"{f.location.path}:{f.location.line}"
    if f.location.end_line and f.location.end_line != f.location.line:
        loc = f"{f.location.path}:{f.location.line}-{f.location.end_line}"

    out = [f"**{f.title}** — `{loc}` _[{f.agent}]_", "", f.explanation]
    if f.suggestion:
        out += ["", "Suggested fix:", "", "```", f.suggestion, "```"]
    return "\n".join(out)


def _render_footer(cost_usd: float, count: int) -> str:
    return (
        "---\n"
        f"_{count} finding{'s' if count != 1 else ''} • "
        f"run cost: ${cost_usd:.4f}_"
    )
