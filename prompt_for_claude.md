# Prompt for Claude — Job Radar AI Review

Copy everything below this line and paste it into Claude, with:
1. Your `jobs_for_gpt.csv` file attached
2. Your resume text pasted below the prompt (or attach resume.txt)

---

## Instructions for Claude

I'm attaching a CSV of job listings and my resume. For each job in the CSV, evaluate whether it's a good fit for me and return the **full CSV** with 4 new columns added.

**Add these columns to every row:**

| Column | Values | Description |
|---|---|---|
| `ai_match` | `yes` / `maybe` / `no` | Is this a good fit for my background? |
| `ai_score` | 0–100 | % match between my resume and this job |
| `ai_stage` | `saved` / `applying` / `new` / `rejected` | Recommended Kanban stage |
| `ai_reason` | 1 sentence | Why you gave this match/score |

**Rules:**
- `ai_stage = applying` → strong fit, I should apply now
- `ai_stage = saved` → decent fit, worth keeping an eye on
- `ai_stage = new` → neutral, not sure yet
- `ai_stage = rejected` → poor fit, overqualified, underqualified, wrong stack
- Keep `job_url` values exactly as-is — they are used to match rows when I import the CSV back
- Return the full CSV including all original columns plus the 4 new ones
- Do not truncate the output — I need every row

**My resume is below:**

[PASTE YOUR RESUME HERE — or attach resume.txt]

---

## After Claude responds

1. Save the CSV Claude returns as a `.csv` file
2. Go to **http://localhost:5001**
3. Click **⬆ Import CSV** in the top bar
4. The Kanban board will update automatically with Claude's recommendations
