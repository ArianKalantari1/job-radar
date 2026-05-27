---
name: job-radar-daily-review
description: Use this skill whenever Ari uploads a jobs_today.csv (or any CSV of scraped job listings) and asks for his top matches. Always trigger on "review today's jobs", "which jobs match", "top jobs from today", "analyse my jobs", or any CSV upload that looks like it came from the job-radar pipeline. This skill encodes Ari's full CV, hard reject rules, match signals, Sydney salary benchmarks, and the exact output format required — including a salary ask column for use directly in application forms. Do not ask Ari to re-paste his CV or preferences — they are already in this skill.
---

# Job Radar — Daily Review Skill

Ari scrapes Australian job listings daily via job-radar. Each morning a fresh `jobs_today.csv` lands in his Desktop/job-rader folder. This skill reads it, evaluates every row against his CV, and returns a ranked top-10 table he can act on immediately.

---

## Step 1: Read the CSV properly

The CSV contains columns: `title`, `company`, `location`, `site`, `primary_role`, `score`, `salary_raw`, `min_amount`, `max_amount`, `match_reasons`, `also_fits`, `resume_match_pct`, `resume_matched_skills`, `resume_missing_skills`, `job_url`, `date_posted`, `first_seen`, `desc_quality`, `description`.

**Non-negotiable rules before starting:**
- Read the full `description` for every single row. Do not truncate or skim.
- **Ignore the `score` column entirely.** It is a rules-based pre-filter, not a fit signal. A low score is not a rejection.
- The CSV already contains only the last 24 hours of jobs (filtered at export time). Every row is fresh — there is no need to filter by date again.
- `min_amount`/`max_amount` are structured salary numbers (AUD, annual). When present, prefer these over parsing `salary_raw` for the salary ask column.
- `resume_missing_skills` is a JSON array of skills the job asks for that are NOT in Ari's resume. Use it to populate the "Biggest gap" column rather than guessing.
- `desc_quality` is `"rich"` (500+ chars), `"partial"` (100-499), or `"stub"` (<100). Discount `"stub"` descriptions — the match signal is unreliable.
- `match_reasons` and `also_fits` are informational context from the rules scorer. They may help as a starting point but always read the full description.

---

## Step 2: Hard reject — exclude these immediately, no exceptions

Remove any job that meets one or more of these criteria before evaluation. Do not surface these in the output at all.

1. **Citizenship / security clearance** — requires Australian citizenship, baseline clearance, NV1, NV2, or states "must be an Australian citizen."
2. **5+ years hands-on engineering as a strict minimum** — phrases like "minimum 5 years", "5+ years required", "at least 6 years of engineering experience." Note: "4+ years in a customer-facing technical role" is fine — Ari qualifies via his AFK consulting tenure.
3. **Purely non-technical** — pure sales, pure account management, pure marketing with no analytical/technical component, pure operations.
4. **Wrong location** — outside Sydney or remote-AU (e.g. "Bangkok", "Singapore", "Melbourne only" with no remote option).

---

## Step 3: Ari's CV — already encoded here, do not ask him to re-paste it

**One-line profile:** Analytics/AI Engineer, 4 years digital delivery consulting + 5-month analytics engineering internship + Master of Data Science (Macquarie, Feb 2026). 485 visa, full working rights. Sydney. Native Japanese speaker.

**Commercial experience:**

**Domain Group** — Analytics Engineer Intern (Jul–Nov 2025, 5 months)
- Snowflake, dbt, Streamlit inside Snowflake
- Rebuilt 2 Tableau dashboards as Streamlit apps used by 10 stakeholders across marketing and senior leadership
- Contributed to dbt models, worked with product and analytics teams on requirements

**AFK Agency** — Digital Project Manager / Implementation Consultant (Jun 2019–Nov 2023, 4 years)
- Owned end-to-end delivery of 10+ digital projects for MINI Australia and BMW
- Automated a manual reporting workflow with Python: 8 hours → 30 minutes
- Led UX redesign using Hotjar, NLP and clustering on user behaviour data
- Launched "Name Your MINI" interactive platform, used nationally
- Coordinated up to 4 Europe-based developers across 2 concurrent client accounts using ClickUp

**Linx Institute** — Sales and Marketing Officer (Dec 2017–Mar 2019)
- Automated CRM workflows in Zoho, built reporting processes

**Active projects:**

**CareerSync** — RAG-based AU resume feedback system (2025–present)
- End-to-end RAG pipeline: FastAPI, ChromaDB, LLM APIs, grounded in AU resume conventions knowledge base
- Three-layer prompt injection defence: input sanitisation + hardened system prompt + output validator that rejects hijacked responses
- Hybrid evaluation engine: rule-based checks (structure, content, language) + AI checks, enforced by schema validation
- Four user-selectable resume templates for post-feedback rebuild

**PatientFlow** — Local AI agent for GP medical documentation (2026–present)
- Product Lead. On-device AI — every step runs locally (healthcare data sovereignty constraint)
- Plus Eight Sprint #3 finalist. Western Sydney AI Innovation Hackathon finalist.
- Pre-revenue, in active GP outreach. Works with Ahmet who leads local inference architecture.

**Stack:** Python · SQL · dbt · Snowflake · FastAPI · Streamlit · Tableau · RAG · LLMs (Claude, OpenAI) · local LLM inference · ChromaDB · vector databases · prompt engineering · evaluation frameworks · prompt injection defence

**Certifications:** dbt Essential. Snowflake Core Associate (in progress).

**Languages:** English (fluent) · Japanese (native)

---

## Step 4: Strong match signals — weight these heavily

- **Explicit stack overlap:** Python, SQL, dbt, Snowflake, FastAPI, Streamlit, RAG, LLMs, vector databases, ChromaDB, LangChain, evaluation frameworks
- **Names Anthropic Claude explicitly** — Ari builds with Claude daily; almost no other candidate at this level can say this
- **Experience level language:** "2–4 years", "mid-level", "associate", "consultant" — not "senior architect" or "principal"
- **Client-facing / implementation / consulting / forward-deployed** — Ari's 4 years at AFK is a direct match
- **GenAI / RAG / agentic AI** — CareerSync and PatientFlow are live demonstrations
- **Japanese language, Japan-facing operations, CJKI markets, Japanese clients** — rare differentiator, weight heavily
- **Startup or small team** — Series A/B, "lean team", "founding role", "build from scratch"
- **AI Product Manager / product lead** — PatientFlow is direct PM-level evidence
- **Prompt injection defence / AI security / evaluation frameworks** — specific CareerSync feature almost unique at this experience level

---

## Step 5: Salary ask — the most important column for Ari

For each job in the top 10, give a specific dollar figure or tight range Ari can type directly into an application form field. This is what **Ari should ask for** — not what the job lists.

**Anchoring rules (apply in order):**

1. If the job **lists a salary range**, anchor inside or just above that range. Don't undersell.
2. If **no salary is listed**, use Sydney market rates:

| Role type | Ari's level (2–4 yrs) |
|---|---|
| Junior/graduate AI or data | $85–95k + super |
| Mid-level data/analytics engineer | $95–115k + super |
| Mid-level AI/GenAI engineer | $105–120k + super |
| Big 4 consultant (Deloitte/KPMG/PwC/EY) | $95–110k + super |
| US-HQ tech company AU office | $110–130k + super |
| Specialist AI/consulting boutique | $100–120k + super |
| AI Product Manager / product lead | $110–125k + super |
| Forward-deployed / implementation engineer | $105–120k + super |

3. **Floor:** Ari should not go below **$95k + super** for any role requiring genuine technical depth.
4. **Flag above-market** — if the role clearly targets 6+ years and the salary reflects that, add "(note: may be targeting more senior candidate)" so Ari calibrates expectations.
5. **Format:** single number or tight two-number range. Always append `+ super`. Example: `$110k + super` or `$105–115k + super`. Never a wide band like "$90–130k".

---

## Step 6: Output format — deliver exactly this, nothing else

### Part 1 — Top 10 table

| Rank | Title | Company | Why it's a match | Biggest gap | Salary ask | URL |
|------|-------|---------|-----------------|-------------|------------|-----|

**Column rules:**
- **Why it's a match:** 2–3 specific reasons that name the actual project, tool, or experience from Ari's CV that maps to this role. Not generic praise.
- **Biggest gap:** Be honest. What will a hiring manager notice is absent? If it's a genuinely clean match, say so briefly.
- **Salary ask:** Paste-ready value. Always includes `+ super`.
- **URL:** Use `job_url` from the CSV verbatim.

### Part 2 — Patterns (3 sentences max, after the table)

- What role types or domains appeared as strong fits across today's batch
- Any role Ari might be underestimating or overlooking in this batch
- Any urgent signal (role posted today at a company he should prioritise)

---

## Behaviour rules

- Do not explain what you are doing step by step. Run the evaluation silently and output the table.
- Do not ask Ari to confirm his CV, preferences, or hard reject rules — they are encoded here.
- If fewer than 10 jobs genuinely match after hard rejects, return fewer than 10. Do not pad with weak matches.
- If the same job appears twice (LinkedIn + Indeed duplicate), merge into one row and use the LinkedIn URL.
- Never use the `score` column as a proxy for fit, even as a tiebreaker. Read the description.
