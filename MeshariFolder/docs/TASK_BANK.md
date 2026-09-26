# The Manager's task bank

## Why

The Manager used to improvise a project, and each week's tasks, from the graduate's CV
alone. The output was sensible, but there was no shared idea of what a good project for
each track looks like, no story running across the weeks, and nothing to point at when
someone asks "why this task?". The task bank is that shared idea: **15 project
seeds** (three each for software engineering, data/AI and cybersecurity; two each for the
other tracks), each with a four-week arc. It is *guidance the Manager adapts*, not a script.

## What is in it

| Track | Seed id | Project | Weeks |
|---|---|---|---|
| software_engineering | `se-booking-platform` | Team Booking Platform | Foundations > Core logic > Users and quality > Ship it |
| software_engineering | `se-support-desk` | Support Ticket Desk | Foundations > Workflow > Usability > Ship it |
| software_engineering | `se-bilingual-events` | Bilingual Event Registration App | Foundations > Two languages > Rules and quality > Ship it |
| data_science_ai | `ds-churn-insights` | Customer Churn Insight Pipeline | Understand the data > Baseline model > Improve and scrutinise > Communicate |
| data_science_ai | `ds-document-qa` | Company Documents Q&A (RAG) | Ingestion > Retrieval and answers > Evaluation > Ship it |
| data_science_ai | `ds-demand-forecast` | Weekly Demand Forecasting | Understand the data > Baseline > Better model > Communicate |
| cybersecurity | `sec-webapp-review` | Vulnerable Web App Security Review | Scope and set up > Find weaknesses > Fix and verify > Report |
| cybersecurity | `sec-api-hardening` | Harden a REST API | Baseline > Identity and input > Operations > Prove it |
| cybersecurity | `sec-soc-monitoring` | Security Monitoring and Incident Response Lab | Build the lab > Detect > Investigate > Report |
| networks_infrastructure | `net-branch-office` | Branch Office Network Design | Requirements and design > Build the core > Secure it > Operate it |
| networks_infrastructure | `net-services-lab` | Internal Services Lab | Build the lab > Core services > Access and safety > Watch it |
| information_systems | `is-leave-workflow` | Employee Leave and Approval Workflow | Requirements > Design > Build > Prove and roll out |
| information_systems | `is-inventory-dashboard` | Inventory and Reporting Dashboard | Understand the business > Model and load > Report > Hand over |
| cloud_devops | `cloud-cicd-service` | CI/CD for a Web Service | Containerise > Automate > Deploy > Operate |
| cloud_devops | `cloud-three-tier-iac` | Three-Tier Infrastructure as Code | Design > Network and compute > Data and security > Cost and resilience |

Each seed has a title, a short brief, the skills it exercises, a four-week **arc** (each
week a *focus* and a *deliverable*: the concrete thing that should exist by the end of the
week) and the **evidence** the graduate submits so the Mentor can see the work. Graduates
on the legacy `junior_dev` track get the software-engineering seeds. The whole bank is one
file, `backend/app/agents/task_bank.py`, written to be edited by the team.

## How the Manager uses it

1. **`create_project`** is shown the seeds for the graduate's *track only*, and told to base
   the project on the best fit for their CV and interests, **adapt** it (a specific name,
   scope and difficulty tuned to their level) and record the choice in `seed_id` (the tool
   restricts it to that track's ids).
2. The choice is stored as `Project.seed_id` (migration `0003`, nullable). An unknown id
   is never stored. `GET /projects/me` returns it: "which seed was this?" is one call.
3. **`plan_week`** is told where the week sits in the arc (focus, deliverable, evidence),
   so week 2 builds on week 1; past the last arc week it is told to extend the project.
4. **Every** plan (with or without a seed) gets the subtask-shaping principles: about a day
   each, independently reviewable, a concrete deliverable, a "done when", and - see the
   next section - README-visible evidence.
5. A graduate's **own project** (Stage 2) has no seed and is planned as before.

## What the Mentor can actually see (this shaped the design)

`github_client.fetch_repo_context` gives the Mentor a repository's description, **the first
25 file paths, and the first 2,000 characters of the README - not the code**. So work whose
proof lives only in the code looks empty to it. Two consequences, both built in:

- every seed's `evidence` says what to put in the README and what to commit (output,
  screenshots, diagrams), and the tests **require** each one to mention the README;
- the Mentor's prompt says what it is shown, and to ask for evidence rather than assume
  something is missing from code it never saw.

For the non-code tracks (networks, information systems) this matters most: the deliverables
are diagrams, configuration and write-ups, which have to be committed as files and shown in
the README to be reviewable.

## Review of the first draft: what changed and why

I reviewed my own first draft against the first real-model run
(`RoomSync - Team Booking Platform`: the Manager adapted the seed rather than copying it, and
its week-1 tasks matched the arc), and changed four things:

1. **Evidence per seed** (new). The Mentor reads only the file list and the README head, so
   each seed now says what to submit so it can be seen.
2. **A defensive security seed** (`sec-soc-monitoring`). Both original security seeds were
   offence or hardening; a monitoring and incident-response seed covers the analyst side.
3. **Two more seeds for the most-used tracks**: a bilingual (Arabic/English, right-to-left)
   event-registration app for software engineering, matching who the demo is for, and a
   demand-forecasting seed for data/AI, so it isn't only churn and RAG.
4. **GitHub rate limit.** Each review costs 3 GitHub requests against an anonymous limit of
   60/hour per IP (about 20 reviews an hour, shared by everyone on one network; a
   `--full-week` check alone uses about 45). `GITHUB_TOKEN` in `backend/.env` raises it to
   5,000/hour, and when the limit *is* hit the Mentor is told it was GitHub's limit, not
   the graduate's fault.

## Rules the tests enforce

`smoke_test_task_bank.py` (62 checks) rejects a bad edit: every track has at least two
seeds (three for the most-used); ids and titles unique slugs; exactly a four-week arc; real
briefs/focus/deliverables; at least three skills; evidence that mentions the README and
GitHub; no placeholder text; a first week about foundations and a last about finishing;
cybersecurity keeps a defensive seed. **To add a seed:** append a `Seed(...)` and run it.

## Decisions for the team

1. **Is this the right set of projects for your audience?** Two seeds each for networks,
   information systems and cloud; add more if those tracks matter in the demo.
2. **Four-week arcs.** A demo probably reaches week 1 or 2; the arc still makes week 2 a
   continuation. The length is a free choice (update the test if you change it).
3. **Level.** Difficulty is tuned to the graduate by the Manager, not by a beginner/advanced
   split.
4. **Stage 3.** A company's own tasks would plug into the same two hooks (seed = the
   company's project, arc = the company's plan).

## Not covered

- **Only week 1 has been seen from a real model.** The wiring is verified and one real run
  adapted a seed well; weeks 2-4 and the other tracks are unproven. Run
  `python e2e_real_llm.py --save-report run1.json` (it prints the project, seed and tasks).
- **The default `--repo` in that script is unrelated** (`psf/requests`), so the Mentor
  correctly scores it 1/5: it exercises the pipeline, not the approve path.
- **Seeds are in English**; with `X-Venv-Language: ar` the Manager writes in Arabic.
- **No starter resources** (repos, datasets) per seed yet.
