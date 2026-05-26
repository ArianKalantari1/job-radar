# Prompt 02 — Role Profiles Config
## Context
You are working on the `job-radar` project. Read `scraper.py` fully before making changes.

The current `SEARCHES` list in `scraper.py` has 20 queries — many for roles (Customer Success Manager, Client Services Manager, Partner Success Manager) that are no longer target roles. We are trimming to 10 searches across 5 role families and extracting them into a config file.

## Task 1 — Create `role_profiles.json`
Create a new file `role_profiles.json` in the project root with this exact content:

```json
{
  "profiles": [
    {
      "id": "data_analyst",
      "label": "Data Analyst",
      "color": "#3b82f6",
      "searches": [
        "data analyst sql python Sydney",
        "business intelligence analyst Sydney"
      ],
      "title_keywords": ["data analyst", "business analyst", "bi analyst", "insights analyst", "reporting analyst", "analytics analyst"],
      "skills_high": ["sql", "tableau", "power bi", "looker", "python", "dbt"],
      "skills_mid": ["excel", "snowflake", "bigquery", "redshift", "stakeholder", "kpi"],
      "seniority_target": ["mid", "senior"],
      "negative_title_signals": ["head of", "director", "vp", "vice president", "chief", "staff"]
    },
    {
      "id": "analytics_engineer",
      "label": "Analytics Engineer",
      "color": "#14b8a6",
      "searches": [
        "analytics engineer dbt Sydney",
        "data engineer python sql Sydney"
      ],
      "title_keywords": ["analytics engineer", "data engineer", "data platform engineer"],
      "skills_high": ["dbt", "snowflake", "bigquery", "airflow", "fivetran", "data modelling"],
      "skills_mid": ["sql", "python", "git", "warehouse", "pipeline", "etl", "elt"],
      "seniority_target": ["mid", "senior"],
      "negative_title_signals": ["head of", "director", "vp", "vice president", "chief", "staff", "principal"]
    },
    {
      "id": "data_scientist",
      "label": "Data Scientist",
      "color": "#8b5cf6",
      "searches": [
        "data scientist machine learning Sydney",
        "AI engineer prompt engineering Sydney"
      ],
      "title_keywords": ["data scientist", "machine learning", "ml engineer", "ai engineer", "applied scientist"],
      "skills_high": ["python", "scikit-learn", "tensorflow", "pytorch", "llm", "nlp", "rag", "vector database", "prompt engineering"],
      "skills_mid": ["sql", "statistics", "experimentation", "jupyter", "pandas", "numpy", "azure", "aws", "gcp"],
      "seniority_target": ["junior", "mid", "senior"],
      "negative_title_signals": ["head of", "director", "vp", "vice president", "chief", "principal"]
    },
    {
      "id": "product_manager",
      "label": "Product Manager (AI/Data)",
      "color": "#f97316",
      "searches": [
        "associate product manager APM Sydney"
      ],
      "title_keywords": ["product manager", "product owner", "associate product manager"],
      "must_also_contain": ["ai", "ml", "machine learning", "data", "analytics", "llm", "platform", "tech"],
      "skills_high": ["roadmap", "prd", "stakeholder", "agile", "user research"],
      "skills_mid": ["jira", "confluence", "figma", "metrics", "kpi", "scrum"],
      "seniority_target": ["junior", "mid"],
      "negative_title_signals": ["head of", "director", "vp", "vice president", "chief", "senior product manager"]
    },
    {
      "id": "project_manager",
      "label": "Project Manager",
      "color": "#6b7280",
      "searches": [
        "project coordinator associate project manager Sydney"
      ],
      "title_keywords": ["project manager", "project coordinator", "delivery manager", "technical project manager", "program manager"],
      "must_also_contain": ["software", "tech", "digital", "data", "it", "agile", "product", "engineering", "platform"],
      "skills_high": ["agile", "scrum", "stakeholder", "delivery", "pmp"],
      "skills_mid": ["jira", "confluence", "risk", "budget", "gantt", "prince2"],
      "seniority_target": ["junior", "mid"],
      "negative_title_signals": ["head of", "director", "vp", "vice president", "chief", "senior project manager"]
    }
  ],
  "also_fits_threshold": 10,
  "score_cap": 100,
  "score_baseline": 50
}
```

## Task 2 — Refactor `SEARCHES` in `scraper.py` to load from `role_profiles.json`

Replace the existing `SEARCHES` list and `SearchConfig` usage with a function that loads from `role_profiles.json`.

At the top of `scraper.py`, add:
```python
import json
```
(only if not already imported)

Replace the hardcoded `SEARCHES: list[SearchConfig] = [...]` block with:

```python
def load_searches_from_profiles(path: Path = Path(__file__).parent / "role_profiles.json") -> list[SearchConfig]:
    """Load search queries from role_profiles.json and return as SearchConfig list."""
    with open(path) as f:
        config = json.load(f)
    searches = []
    for profile in config["profiles"]:
        for query in profile["searches"]:
            searches.append(SearchConfig(
                label=profile["label"],
                search_term=query,
            ))
    return searches

SEARCHES: list[SearchConfig] = load_searches_from_profiles()
```

Do not change the `SearchConfig` dataclass definition. Do not change anything else in `scraper.py`.

## Task 3 — Smoke test the new searches
After making changes, run:
```bash
python -c "from scraper import SEARCHES; print(f'{len(SEARCHES)} searches loaded:'); [print(f'  {s.label}: {s.search_term}') for s in SEARCHES]"
```
Expected output: exactly 10 searches, one per query in `role_profiles.json`.

## Do NOT
- Do not modify `upsert_jobs()`, `init_db()`, `fetch_description()`, or `enrich_descriptions()`
- Do not change the `SearchConfig` dataclass
- Do not remove the `SENIOR_TITLE_BLOCKLIST` or `is_too_senior()` function
- Do not touch `scorer.py`, `dashboard.py`, or `run.py`
