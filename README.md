# coverage-radar

Turn a pile of feeds into a brief that knows what it has already told you.

It collects coverage, groups articles about the same event into one story, scores each story on theme, breadth and freshness, and writes a Markdown brief plus JSON and CSV. The archive means the second run is smarter than the first: it can tell you what is new, and whether a topic is busier than usual.

```
$ coverage-radar run
2026-11-12T09:45:00+00:00 · last 48h: 40 articles from 3 outlets · 40 stories (2 lead, 5 brief)
brief: out/brief.md
```

## Why

A feed reader gives you 400 headlines and no judgement. Worse, it cannot answer the two questions that actually matter to a communications desk:

1. **Is this being said by more than one outlet?** One outlet is an item. Five outlets is a story with weight behind it.
2. **Is this new?** The same event reappearing every morning is noise, and a quiet week on your priority theme is a finding, not an empty section.

Third, and the one most briefs miss: **who else is carrying this theme?** Share of voice counts distinct outlets per watchlist theme — the breadth signal that survives differently-worded headlines, where headline matching alone does not.

`coverage-radar` answers all three because it keeps an archive, counts outlets per story rather than per article, and prints the reasons for every score. No model is called at any point: the same inputs produce the same brief, and every point can be traced to a rule you can change.

## Install

Python 3.9 or later. Nothing else, no API keys.

```bash
git clone https://github.com/sadok-ayari/coverage-radar.git
cd coverage-radar
python -m covradar run
```

Or install the command:

```bash
pip install -e .
coverage-radar run
```

## What comes out

| File | Contents |
|---|---|
| `out/brief.md` | the brief: failed sources first, then lead stories, briefs, theme movement, coverage gaps, source mix |
| `out/stories.json` | every story with its outlets, links, themes, tone, salience and reasons |
| `out/stories.csv` | one row per story, ranked, for a spreadsheet or a chart |

A real run is committed at [examples/brief-example.md](examples/brief-example.md).

## How a story is scored

| Component | Default | Rule |
|---|---|---|
| theme | 35 | keyword hit in the watchlist; 25 for the first theme, +5 per extra |
| breadth | 25 | 8 points per additional outlet, capped — one outlet scores nothing |
| recency | 20 | under 24h: 20 · under 48h: 12 · older: 3 · time not stated: 5 |
| novelty | 10 | full marks only if the story is not already in the archive |

`lead` at 60 and above, `brief` at 45. If `require_theme_for_brief` is on, a story outside the watchlist is logged but never lifted into the brief — relevance is a gate, not a nudge.

## Configuration

`config/watchlist.json` — what you care about:

```json
{
  "window_hours": 48,
  "themes": [{"name": "climate finance", "keywords": ["climate finance", "green bond"]}],
  "weights": {"theme": 35, "breadth": 25, "novelty": 10, "recency_24h": 20,
              "recency_48h": 12, "recency_old": 3, "recency_unknown": 5},
  "thresholds": {"lead": 60, "brief": 45},
  "require_theme_for_brief": true
}
```

`config/sources.json` — where coverage comes from. Two adapter types ship:

| Type | For | Notes |
|---|---|---|
| `rss` | any RSS or Atom feed | `outlet` overrides the feed's own title |
| `gdelt` | the GDELT DOC 2.0 API, thousands of outlets by query | rate limited to about one request every five seconds; disabled by default |

Adding an outlet is a config block. Write a new adapter only when a source offers neither a feed nor an API.

## Commands

```bash
coverage-radar run                          # the normal run
coverage-radar run --window 72               # look back three days
coverage-radar run --now 2026-11-12T09:00Z   # fix the clock, replay a decision
coverage-radar run --dry-run                 # brief without touching the archive
coverage-radar run --offline --cache .cache  # replay cached responses
coverage-radar collect                       # fetch and cache only
coverage-radar sources                       # what is configured, and whether it is on
```

`--json` prints the run summary as data, which is what a scheduler should log.

## Design decisions

- **Stories, not articles.** One event on five outlets is one line in the brief with five links, because the number of outlets is the signal.
- **The archive is the memory.** `coverage.db` (SQLite) keeps articles, stories, daily theme counts and run records. Novelty and "busier than usual" both come from it.
- **A failed source is reported first,** in the brief and in the run record. A brief that silently drops an outlet is worse than a short brief.
- **Tone is labelled indicative** because it is a lexicon count: it cannot read irony, attribution or quotation. It is a sorting aid, not a finding.
- **No dependencies, no model calls.** A clean clone runs on the system Python, indoors, in a locked-down environment.

## Honest limits

- Clustering is headline token overlap. It merges syndicated copy and light rewrites; a full paraphrase of the same event can stay separate. Fixing that needs embeddings, which would mean models and a heavier install — a different project.
- Lexical theme matching misses a genuinely relevant story that uses none of your keywords. When that happens the fix is a keyword in `watchlist.json`, not code.
- GDELT returns prose when you exceed its rate limit, not an HTTP error, so the adapter treats a non-JSON body as a failure and says so.
- Only English feeds are configured by default. Nothing in the code is English-specific except the tone lexicon and stopword list.

## Tests

```bash
python -m unittest discover -s tests      # 68 tests, offline, no network
```

CI runs the suite on Python 3.9, 3.11 and 3.13, then smoke-tests the CLI.

## Licence

MIT — see [LICENSE](LICENSE).
