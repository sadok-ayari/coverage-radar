"""Command line entry point.

    coverage-radar run
    coverage-radar run --now 2026-11-12T09:00Z --window 48
    coverage-radar run --offline --cache .cache
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import __version__, pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coverage-radar",
        description="Collect coverage, cluster it into stories, score salience, write a brief.",
    )
    parser.add_argument("--version", action="version", version=f"coverage-radar {__version__}")
    sub = parser.add_subparsers(dest="command")

    run_cmd = sub.add_parser("run", help="collect, cluster, score and write the brief")
    run_cmd.add_argument("--config", default="config")
    run_cmd.add_argument("--out", default="out")
    run_cmd.add_argument("--now", default=None, help="YYYY-MM-DD or ISO timestamp; fixes the clock")
    run_cmd.add_argument("--window", type=int, default=None, help="hours to look back (default from watchlist.json)")
    run_cmd.add_argument("--offline", action="store_true")
    run_cmd.add_argument("--cache", default=".cache")
    run_cmd.add_argument("--db", default="coverage.db")
    run_cmd.add_argument("--dry-run", action="store_true", help="do not write to the archive")
    run_cmd.add_argument("--json", action="store_true")

    collect_cmd = sub.add_parser("collect", help="fetch and cache, no analysis")
    collect_cmd.add_argument("--config", default="config")
    collect_cmd.add_argument("--cache", default=".cache")
    collect_cmd.add_argument("--json", action="store_true")

    sub.add_parser("sources", help="list configured sources")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "sources":
        cfg = pipeline.load_json(f"{getattr(args, 'config', 'config')}/sources.json")
        for source in cfg.get("sources", []):
            state = "on " if source.get("enabled", True) else "off"
            print(f"[{state}] {source.get('name'):<28} {source.get('type', 'rss'):<7} "
                  f"tier {source.get('tier', 3)}  {source.get('url', '')}")
        return 0

    if command == "collect":
        cfg = pipeline.load_json(f"{args.config}/sources.json").get("sources", [])
        articles, runs = pipeline.collect(cfg, offline=False, cache_dir=args.cache)
        if args.json:
            print(json.dumps({"articles": len(articles), "sources": [r.to_dict() for r in runs]}, indent=2))
        else:
            for run in runs:
                print(f"{'ok  ' if run.ok else 'FAIL'} {run.name}: {run.count} item(s)"
                      + (f" — {run.error}" if run.error else ""))
        return 0 if any(r.ok for r in runs) else 2

    try:
        summary = pipeline.run(
            config_dir=args.config, out_dir=args.out, now=args.now,
            window_hours=args.window, offline=args.offline, cache_dir=args.cache,
            db_path=args.db, mark=not args.dry_run,
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['now']} · last {summary['window_hours']}h: {summary['articles']} articles from "
              f"{summary['outlets']} outlets · {summary['stories']} stories "
              f"({summary['lead']} lead, {summary['brief']} brief)")
        if summary["failed_sources"]:
            print("failed sources: " + ", ".join(summary["failed_sources"]))
        print(f"brief: {summary['brief_path']}")
    return 0 if len(summary["failed_sources"]) < summary["sources_polled"] or not summary["sources_polled"] else 2
