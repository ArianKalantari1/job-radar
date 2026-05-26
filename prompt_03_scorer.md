# Prompt 03 — Multi-Role Scorer
## Context
You are working on the `job-radar` project. Read `scorer.py`, `role_profiles.json`, and `scraper.py` fully before making changes.

The current `scorer.py` uses a single flat keyword list. We are replacing it with a multi-role scoring engine that:
1. Scores each job against all 5 role profiles in `role_profiles.json`
2. Assigns a `primary_role` (best-matching profile)
3. Tags any other profiles within 10 points as `also_fits`
4. Produces plain-English `match_reasons`
5. Stores per-profile score breakdown in `role_scores`

## Task — Rewrite `scorer.py` completely

Replace the entire contents of `scorer.py` with the following. Do not keep the old `SKILLS_STRONG`, `SKILLS_NICE`, `DOMAIN_BONUS`, or `TITLE_PENALTIES` — they are superseded by `role_profiles.json`.

```python
"""
job-radar: multi-role scoring module

Scores each job against all role profiles defined in role_profiles.json.
Assigns primary_role (best fit), also_fits (within threshold), and match_reasons.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
PROFILES_PATH = Path(__file__).parent / "role_profiles.json"
PERSONALIZED_PROFILES_PATH = Path(__file__).parent / "role_profiles_personalized.json"

SALARY_FLOOR = int(os.getenv("SALARY_FLOOR_AUD", "140000"))
SALARY_PENALTY_NO_DATA = int(os.getenv("SALARY_PENALTY_NO_DATA", "20"))
SALARY_PENALTY_PER_10K = int(os.getenv("SALARY_PENALTY_PER_10K_BELOW", "5"))

YOE_PATTERNS = [
    (r"\b(8|9|10)\+?\s*years?\b", -10, "8+ years experience required"),
    (r"\b7\+?\s*years?\b", -6, "7+ years experience required"),
    (r"\b6\+?\s*years?\b", -4, "6+ years experience required"),
    (r"\b5\+?\s*years?\b", -2, "5+ years experience required"),
    (r"\b(graduate|junior|entry[\s-]level|entry level)\b", +5, "Entry/junior level role"),
    (r"\b(2|3)\+?\s*years?\b", +3, "2-3 years experience (good fit)"),
]


def _load_profiles() -> dict:
    """Load personalized profiles if available, else base profiles."""
    path = PERSONALIZED_PROFILES_PATH if PERSONALIZED_PROFILES_PATH.exists() else PROFILES_PATH
    with open(path) as f:
        return json.load(f)


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _title_matches_profile(title_l: str, profile: dict) -> bool:
    """Return True if the job title matches at least one of the profile's title keywords."""
    keywords = profile.get("title_keywords", [])
    if not keywords:
        return True
    return any(kw in title_l for kw in keywords)


def _must_also_contain(combined: str, profile: dict) -> bool:
    """For PM profiles: the combined text must also contain at least one context keyword."""
    required = profile.get("must_also_contain")
    if not required:
        return True
    return any(kw in combined for kw in required)


def _score_skills(combined: str, profile: dict) -> tuple[int, list[str]]:
    """Score skill matches. Returns (points, reasons)."""
    points = 0
    reasons = []
    for skill in profile.get("skills_high", []):
        if skill in combined:
            points += 6
            reasons.append(f"+6 key skill: {skill}")
    for skill in profile.get("skills_mid", []):
        if skill in combined:
            points += 2
            reasons.append(f"+2 skill: {skill}")
    return points, reasons


def _score_seniority(title_l: str, desc_l: str, profile: dict) -> tuple[int, list[str]]:
    """Score seniority fit. Returns (delta, reasons)."""
    points = 0
    reasons = []

    # Penalise negative title signals (too senior)
    for signal in profile.get("negative_title_signals", []):
        if signal in title_l:
            points -= 15
            reasons.append(f"-15 too senior: '{signal}' in title")
            return points, reasons  # one penalty is enough

    # YoE patterns in description
    for pattern, delta, label in YOE_PATTERNS:
        if re.search(pattern, desc_l):
            points += delta
            reasons.append(f"{delta:+d} {label}")
            break

    return points, reasons


def _score_salary(salary_min: float | None, salary_max: float | None) -> tuple[int, list[str]]:
    """Score salary fit against SALARY_FLOOR. Returns (delta, reasons)."""
    if not salary_min and not salary_max:
        return -SALARY_PENALTY_NO_DATA, [f"-{SALARY_PENALTY_NO_DATA} salary not listed"]

    best = salary_max or salary_min
    if best >= SALARY_FLOOR:
        return +10, [f"+10 salary ${int(best):,} meets floor (${SALARY_FLOOR:,})"]

    gap = SALARY_FLOOR - best
    penalty = min(25, int((gap / 10000) * SALARY_PENALTY_PER_10K))
    return -penalty, [f"-{penalty} salary ${int(best):,} below floor (${SALARY_FLOOR:,})"]


def _score_location(location: str | None) -> tuple[int, list[str]]:
    """Score location fit for Sydney + AU remote."""
    loc_l = _norm(location)
    if not loc_l:
        return 0, []
    if "sydney" in loc_l:
        return +10, ["+10 Sydney location"]
    if "remote" in loc_l or "australia" in loc_l or "au" in loc_l:
        return +5, ["+5 AU remote or Australia-wide"]
    return -10, ["-10 location outside Sydney/AU"]


def score_job_against_profile(
    title: str | None,
    description: str | None,
    location: str | None,
    salary_min: float | None,
    salary_max: float | None,
    profile: dict,
    config: dict,
) -> tuple[int, list[str]]:
    """
    Score a job against a single role profile.
    Returns (score, reasons). Score is 0 if the job doesn't match the profile title.
    """
    title_l = _norm(title)
    desc_l = _norm(description)
    combined = f"{title_l} {desc_l}"

    # Hard gate: title must match profile
    if not _title_matches_profile(title_l, profile):
        return 0, ["title does not match this role profile"]

    # Hard gate: PM roles require context keywords
    if not _must_also_contain(combined, profile):
        return 0, ["missing required context (AI/data/tech) for this role type"]

    baseline = config.get("score_baseline", 50)
    score = baseline
    reasons = []

    skill_pts, skill_reasons = _score_skills(combined, profile)
    score += skill_pts
    reasons.extend(skill_reasons[:5])  # cap at 5 skill reasons for readability

    seniority_pts, seniority_reasons = _score_seniority(title_l, desc_l, profile)
    score += seniority_pts
    reasons.extend(seniority_reasons)

    salary_pts, salary_reasons = _score_salary(salary_min, salary_max)
    score += salary_pts
    reasons.extend(salary_reasons)

    location_pts, location_reasons = _score_location(location)
    score += location_pts
    reasons.extend(location_reasons)

    cap = config.get("score_cap", 100)
    score = max(0, min(cap, score))
    return score, reasons


def score_job(
    title: str | None,
    description: str | None,
    location: str | None,
    salary_min: float | None,
    salary_max: float | None,
) -> dict:
    """
    Score a job against all role profiles. Returns a result dict with:
    - score: int (primary role's score)
    - primary_role: str (profile id of best match)
    - also_fits: list[str] (profile ids within threshold of primary)
    - role_scores: dict (all profile scores)
    - match_reasons: list[str] (reasons for primary role)
    """
    config = _load_profiles()
    profiles = config["profiles"]
    threshold = config.get("also_fits_threshold", 10)

    all_scores: dict[str, int] = {}
    all_reasons: dict[str, list[str]] = {}

    for profile in profiles:
        s, r = score_job_against_profile(
            title, description, location, salary_min, salary_max, profile, config
        )
        all_scores[profile["id"]] = s
        all_reasons[profile["id"]] = r

    # Primary role = highest score
    primary_id = max(all_scores, key=lambda k: all_scores[k])
    primary_score = all_scores[primary_id]

    # Also fits = any other profile within threshold (and score > 0)
    also_fits = [
        pid for pid, s in all_scores.items()
        if pid != primary_id and s > 0 and (primary_score - s) <= threshold
    ]

    return {
        "score": primary_score,
        "primary_role": primary_id,
        "also_fits": also_fits,
        "role_scores": all_scores,
        "match_reasons": all_reasons[primary_id],
    }


def score_all_jobs() -> int:
    """Score every job in the DB against all role profiles. Returns count of jobs scored."""
    config = _load_profiles()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT job_url, title, description, location, min_amount, max_amount FROM jobs"
    ).fetchall()

    count = 0
    for job_url, title, description, location, min_amount, max_amount in rows:
        result = score_job(title, description, location, min_amount, max_amount)

        conn.execute(
            """
            UPDATE jobs SET
                score = ?,
                primary_role = ?,
                also_fits = ?,
                role_scores = ?,
                match_reasons = ?,
                score_reasons = ?
            WHERE job_url = ?
            """,
            (
                result["score"],
                result["primary_role"],
                json.dumps(result["also_fits"]),
                json.dumps(result["role_scores"]),
                json.dumps(result["match_reasons"]),
                " | ".join(result["match_reasons"][:6]),  # backward compat with old dashboard
                job_url,
            ),
        )
        count += 1

    conn.commit()
    conn.close()
    return count


if __name__ == "__main__":
    n = score_all_jobs()
    print(f"scored {n} jobs")
```

## Validation
Run:
```bash
python run.py --no-scrape
```

Then run this audit:
```bash
python -c "
import sqlite3, json
conn = sqlite3.connect('jobs.db')
rows = conn.execute('SELECT title, score, primary_role, also_fits FROM jobs ORDER BY score DESC LIMIT 15').fetchall()
for r in rows:
    print(f'{r[2]:25} | {r[1]:3} | {r[0][:50]}')
    if r[3] and r[3] != '[]':
        print(f'  also fits: {r[3]}')
conn.close()
"
```

Expected: every row has a `primary_role` that is one of: `data_analyst`, `analytics_engineer`, `data_scientist`, `product_manager`, `project_manager`. Scores should be 0–100 (no 101+). Jobs with mismatched titles should score 0 or very low.

## Do NOT
- Do not modify `scraper.py`, `run.py`, or `dashboard.py`
- Do not keep the old `SKILLS_STRONG` / `SKILLS_NICE` lists anywhere
- Do not add LLM API calls in this prompt — that is a later phase
