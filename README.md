# AI Job Exposure Explorer (trial prototype)

How exposed are today's jobs to AI? This app labels job postings as **exposed**, **augmented**, or **resistant** to AI, shows how much the label varies inside each sector and role, and compares exposure with how hiring has changed since the postings were collected.

**Live app:** https://ai-job-exposure.streamlit.app

> **Prototype.** It runs on sample data: the first 100 postings of the Kaggle file (93 after cleaning), listed April 5–19, 2024, labeled by Claude following our labeling prompt (v1). The trial run will relabel a random sample with an LLM through the Groq API, using the notebook in our team folder.

## How a posting is labeled

The model lists the job's 3–6 main tasks and rates each one: *AI can do it*, *AI can help*, or *needs a person*. A fixed rule (not the model) turns the ratings into a label:

| Rule, checked in order | Label |
|---|---|
| Half or more of the tasks need a person | Resistant |
| Half or more of the tasks AI can do | Exposed |
| Everything else | Augmented |

The **exposure score** (0 to 1) is (tasks AI can do + half of the tasks AI can help) / all tasks.

## What the app shows

- **Overview:** the overall label mix, and each sector's exposure score against its hiring change compared with the whole market (Indeed).
- **Explore a role:** the number of postings, the label mix, top skills, the sector's hiring trend, and example postings with their task ratings.
- **Check a job posting:** paste a posting to label it (needs a `GROQ_API_KEY` in the app's secrets).
- **How it works:** label definitions, the AI-mention trend, and limits. "Last built on" is shown at the top of every page.

## Data

- Kaggle, [LinkedIn Job Postings (2023–2024)](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings), arshkon.
- Indeed Hiring Lab [AI Tracker](https://github.com/hiring-lab/ai-tracker) and [Job Postings Index by sector](https://github.com/hiring-lab/job_postings_tracker), CC BY 4.0.

## Files

- `app.py`: the Streamlit app
- `app_data/`: files written by the pipeline notebook (labeled postings, sector summary, Indeed AI share, build info with the prompt)
- `requirements.txt`

## Limits

- **Selection:** postings only show jobs that are still being hired. Roles that AI already reduced may be missing, so the most affected jobs can look less exposed.
- **AI-written postings:** many postings are written with AI tools. Labels come from tasks, not wording, and AI in the job duties is counted separately from AI in company boilerplate.
- **Snapshot:** labels reflect the posting dates shown in the app.
