"""Markdown brief."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Sequence

from .models import SourceRun, Story
from .textutil import human_age


def _format_now(now: datetime) -> str:
    return now.strftime("%d %b %Y, %H:%M UTC")


def _lead_block(story: Story, now: datetime) -> str:
    lines = [f"### {story.lead.title}"]
    lines.append(f"- **Outlets ({story.outlet_count}):** " + ", ".join(story.outlets))
    lines.append(f"- **Published:** {story.lead.published or 'time not stated'} · {human_age(story.lead.published, now)}")
    if story.themes:
        lines.append("- **Themes:** " + ", ".join(story.themes))
    lines.append(f"- **Tone:** {story.tone}")
    lines.append(f"- **Salience {story.salience} — {story.verdict}:** " + " · ".join(story.reasons))
    links = [f"[{a.outlet}]({a.url})" for a in story.articles[:4]]
    lines.append("- **Links:** " + " · ".join(links))
    return "\n".join(lines)


def render(
    stories: Sequence[Story],
    sources: Sequence[SourceRun],
    now: datetime,
    *,
    window_hours: int,
    article_count: int,
    outlet_count: int,
    title: str = "Coverage brief",
    velocity: Dict[str, Dict] | None = None,
    gaps: List[str] | None = None,
    mix: Dict[str, int] | None = None,
    voice: Dict[str, Dict] | None = None,
    dropped_undated: int = 0,
) -> str:
    leads = [s for s in stories if s.verdict == "lead"]
    briefs = [s for s in stories if s.verdict == "brief"]
    logged = [s for s in stories if s.verdict == "log"]
    failed = [s for s in sources if not s.ok]

    out: List[str] = [f"# {title} — {_format_now(now)}", ""]
    out.append(
        f"**Window: last {window_hours}h · {article_count} articles from {outlet_count} outlets · "
        f"{len(stories)} stories · {len(leads)} lead, {len(briefs)} brief, {len(logged)} logged.**"
    )

    if failed:
        out += ["", "## Sources that failed", ""]
        out += [f"- **{run.name}** — {run.error}" for run in failed]
        out += ["", "*This brief is incomplete: the sources above were not read.*"]

    out += ["", f"## Lead stories ({len(leads)})", ""]
    if not leads:
        out.append("_No story cleared the lead threshold this window._")
    for story in leads:
        out += [_lead_block(story, now), ""]

    out += [f"## Brief ({len(briefs)})", ""]
    if not briefs:
        out.append("_Nothing at brief level._")
    for story in briefs:
        themes = ", ".join(story.themes) if story.themes else "outside watchlist"
        out.append(
            f"- **{story.lead.title}** — {story.outlet_count} outlet{'s' if story.outlet_count != 1 else ''}, "
            f"{human_age(story.lead.published, now)}, {themes}, salience {story.salience}. "
            f"[{story.outlets[0]}]({story.lead.url})"
        )

    if voice:
        out += ["", "## Share of voice", "",
                "_Watchlist themes, ranked by how many distinct outlets carried them this window._"]
        for theme, data in voice.items():
            outlets = ", ".join(f"{name} ({count})" for name, count in data["top_outlets"])
            stories_n = data["stories"]
            outlets_n = data["outlets"]
            out.append(
                f"- **{theme}:** {stories_n} {'story' if stories_n == 1 else 'stories'} across "
                f"{outlets_n} {'outlet' if outlets_n == 1 else 'outlets'} — {outlets}"
            )

    if velocity:
        out += ["", "## Theme movement", ""]
        for theme, data in sorted(velocity.items(), key=lambda kv: kv[1]["count"], reverse=True):
            out.append(f"- **{theme}:** {data['count']} today — {data['note']}")

    if gaps:
        out += ["", "## Coverage gaps", ""]
        out.append("_Watchlist themes with no coverage in this window — absence is a finding, "
                   "not an empty section._")
        out.append("- " + " · ".join(gaps))

    if mix:
        out += ["", "## Source mix", ""]
        for outlet, count in list(mix.items())[:12]:
            out.append(f"- {outlet}: {count}")

    notes: List[str] = []
    if dropped_undated:
        notes.append(f"{dropped_undated} item(s) carried no publication time and were excluded from the window.")
    notes.append("Tone is a lexicon count and is indicative only; it cannot read irony or quotation.")
    notes.append("Clusters are token overlap on headlines. A cluster is evidence of one event, not proof of agreement.")
    out += ["", "---", ""] + [f"- {note}" for note in notes]
    return "\n".join(out).strip() + "\n"
