"""
The Manager's task bank: project SEEDS, each with a four-week ARC.

Until now the Manager improvised a project and each week's tasks from the
graduate's CV alone. That produced sensible output (real-model runs gave
things like "SecureBook: Full-Stack Booking Platform"), but with no shared idea
of what a good project for each track looks like, no story across weeks, and
nothing to point to when someone asks "why this task?". This module is that
shared idea.

How it is used (agents/manager.py):
  * create_project offers the graduate's track's seeds and asks the Manager to
    base the project on the best fit, ADAPTED to their CV and level - the seed is
    guidance, never a script. The choice is stored as Project.seed_id.
  * plan_week tells the Manager which arc step this week is (its focus and the
    deliverable that should exist by Thursday), so week 2 builds on week 1.
  * a graduate's own project (Stage 2) has no seed and is planned as before.

This is a first draft written for the team to edit: change wording, swap or add
seeds, re-order an arc. Nothing else needs to change. Rules that the tests
enforce (docs/TASK_BANK.md): every track has at least two seeds, every seed has
a four-week arc, every week has a focus and a concrete deliverable.
"""
import copy
from dataclasses import dataclass

from app.agents.tools import CREATE_PROJECT_TOOL
from app.models import TrackEnum


@dataclass(frozen=True)
class WeekArc:
    focus: str  # what this week is about
    deliverable: str  # what should exist and be checkable by the end of the week


@dataclass(frozen=True)
class Seed:
    id: str
    track: TrackEnum
    title: str
    brief: str
    skills: tuple[str, ...]
    arc: tuple[WeekArc, ...]
    # What the graduate submits so the Mentor can SEE the work. The Mentor is shown a
    # repository's file list (first 25 files) and the start of its README (about 2,000
    # characters), plus any notes or screenshots - not the code itself - so anything to
    # be judged must be visible there. See github_client.fetch_repo_context.
    evidence: str


T = TrackEnum

# A graduate's own-project materials (router) are capped to this many characters
# combined before being stored, and this is what the Manager's prompt is told the
# cap is — a few pages, generous for a project brief, small enough to keep every
# week's prompt a predictable size.
MAX_MATERIALS_CHARS = 6000

SEEDS: tuple[Seed, ...] = (
    # ------------------------------------------------------------------ software engineering
    Seed(
        id="se-booking-platform",
        track=T.SOFTWARE_ENGINEERING,
        title="Team Booking Platform",
        brief=(
            "A small booking system for shared resources (meeting rooms, equipment): a REST API "
            "with users, bookings and conflict detection, a simple client, and a deployed demo."
        ),
        skills=("REST API design", "relational data modelling", "authentication", "automated testing", "CI"),
        arc=(
            WeekArc("Foundations: repo, local environment, data model and the first endpoint.",
                    "A running API with a health check and one CRUD resource, plus a README that says how to run it."),
            WeekArc("Core logic: booking rules, overlap/conflict detection, validation and error handling.",
                    "A bookings API whose overlap rules are covered by automated tests."),
            WeekArc("Users and quality: authentication and authorisation, logging, and continuous integration.",
                    "Login and protected endpoints, with a CI pipeline that runs the tests on every push."),
            WeekArc("Ship it: a minimal UI or complete API docs, deployment, and a demo.",
                    "A deployed (or containerised) app, a short demo walkthrough and a list of known limitations."),
        ),
        evidence='A GitHub repository with the code, tests and a README that says what was done and how to run and test it; screenshots or command output showing it running.',
    ),
    Seed(
        id="se-support-desk",
        track=T.SOFTWARE_ENGINEERING,
        title="Support Ticket Desk",
        brief=(
            "A helpdesk application: customers open tickets, agents triage and comment, statuses "
            "move through a workflow, and managers see simple metrics."
        ),
        skills=("web application structure", "state machines / workflows", "search and filtering", "testing", "code review"),
        arc=(
            WeekArc("Foundations: project structure, ticket data model, create and list tickets.",
                    "Working create/list/detail for tickets, with a short design note explaining the data model."),
            WeekArc("Workflow: status transitions, assignment, comments and permission rules.",
                    "A ticket lifecycle that rejects invalid transitions, with tests for the transition rules."),
            WeekArc("Usability: search, filters, pagination and notifications.",
                    "Searchable, filterable ticket lists and at least one notification path, tested."),
            WeekArc("Ship it: metrics view, polish, deployment and a walkthrough.",
                    "A deployed app with a metrics page and a walkthrough of one ticket from open to closed."),
        ),
        evidence='A GitHub repository with the code, tests and a README that says what was done and how to run and test it; screenshots or command output showing it running.',
    ),
    Seed(
        id="se-bilingual-events",
        track=T.SOFTWARE_ENGINEERING,
        title="Bilingual Event Registration App",
        brief=(
            "A registration app for community events that works properly in Arabic and English: attendees "
            "sign up and get a confirmation, organisers manage capacity and a waitlist, and check-in uses a code."
        ),
        skills=("REST API design", "internationalisation and right-to-left layouts", "validation and capacity rules", "automated testing", "deployment"),
        arc=(
            WeekArc("Foundations: repo, environment, the event and attendee data model, and the first registration endpoint.",
                    "A running API where an attendee can register for an event, with a README that says how to run it."),
            WeekArc("Two languages: a simple registration form in Arabic and English, including right-to-left layout.",
                    "A form that switches between Arabic (right-to-left) and English, with validation messages in both languages."),
            WeekArc("Rules and quality: capacity limits, a waitlist and automated tests.",
                    "Capacity and waitlist rules covered by tests, including the last-seat and duplicate-registration cases."),
            WeekArc("Ship it: check-in with a code, deployment and a demo.",
                    "A deployed or containerised app, a working check-in flow and a short demo walkthrough."),
        ),
        evidence='A GitHub repository with the code, tests and a README that says how to run it; screenshots of the registration form in both Arabic and English.',
    ),
    # ------------------------------------------------------------------ data science / AI
    Seed(
        id="ds-churn-insights",
        track=T.DATA_SCIENCE_AI,
        title="Customer Churn Insight Pipeline",
        brief=(
            "Take a customer dataset, clean and explore it, build and evaluate a model that predicts "
            "who is likely to leave, and turn the result into a recommendation a manager can act on."
        ),
        skills=("data cleaning", "exploratory analysis", "feature engineering", "model evaluation", "communicating results"),
        arc=(
            WeekArc("Understand the data: acquire, clean and explore it.",
                    "A clean dataset and an exploration notebook summarising five concrete findings."),
            WeekArc("Baseline model: features, a train/test split and a first model with honest metrics.",
                    "A reproducible training script and a baseline result with the metrics explained."),
            WeekArc("Improve and scrutinise: compare models, guard against leakage, analyse errors.",
                    "A model comparison table and a written error analysis of where the model fails."),
            WeekArc("Communicate: package the model and explain it to a non-technical reader.",
                    "A prediction script or endpoint and a one-page recommendation for a manager."),
        ),
        evidence='A GitHub repository or notebook with the code, charts and results, and a README with a short written summary of what was found.',
    ),
    Seed(
        id="ds-document-qa",
        track=T.DATA_SCIENCE_AI,
        title="Company Documents Q&A (RAG)",
        brief=(
            "Build an assistant that answers questions from a set of company documents, citing where "
            "each answer came from, and measure how well it actually works."
        ),
        skills=("text processing and chunking", "embeddings and retrieval", "prompting", "evaluation design", "API design"),
        arc=(
            WeekArc("Ingestion: load documents, clean them and split them into sensible chunks.",
                    "An ingestion script and a chunking approach justified with examples."),
            WeekArc("Retrieval and answers: embed, retrieve the best chunks and generate cited answers.",
                    "A working question-answering function that returns an answer with its sources."),
            WeekArc("Evaluation: build a small question set and study where answers go wrong.",
                    "An evaluation set with scores and a written analysis of the failure cases."),
            WeekArc("Ship it: wrap it in a small API or UI and note cost and latency.",
                    "A runnable service, a demo, and a note on cost, speed and limitations."),
        ),
        evidence='A GitHub repository with the code, the evaluation questions and their scores, and a README that says what works and where it fails.',
    ),
    Seed(
        id="ds-demand-forecast",
        track=T.DATA_SCIENCE_AI,
        title="Weekly Demand Forecasting",
        brief=(
            "Forecast next week's demand for a product from its sales history: explore the data, build a "
            "baseline and a better model, measure them honestly, and present a forecast a planner could use."
        ),
        skills=("time-series analysis", "baseline and model comparison", "backtesting", "visualisation", "communicating uncertainty"),
        arc=(
            WeekArc("Understand the data: load the sales history, clean it and explore trend and seasonality.",
                    "A clean dataset and a notebook with charts showing the trend, seasonality and any gaps."),
            WeekArc("Baseline: a simple forecast and a proper backtest to measure it.",
                    "A baseline forecast (for example last week or a moving average) with backtest errors reported."),
            WeekArc("Better model: add seasonality or features and compare against the baseline honestly.",
                    "A comparison of models on the same backtest, with a written explanation of which wins and why."),
            WeekArc("Communicate: package the forecast and explain its uncertainty to a planner.",
                    "A script or notebook that produces next week's numbers with a range, and a one-page summary."),
        ),
        evidence='A GitHub repository or notebook with the code, charts and backtest results, and a README with a short written summary of the forecast.',
    ),
    # ------------------------------------------------------------------ cybersecurity
    Seed(
        id="sec-webapp-review",
        track=T.CYBERSECURITY,
        title="Vulnerable Web App Security Review",
        brief=(
            "Set up an intentionally vulnerable web application in a safe local lab, find and document "
            "its weaknesses the way a security consultant would, and recommend how to fix them."
        ),
        skills=("threat modelling", "OWASP Top 10", "vulnerability documentation", "remediation", "reporting"),
        arc=(
            WeekArc("Scope and set up: rules of engagement, a safe local lab and a simple threat model.",
                    "A working lab, a written scope and a threat model of the application."),
            WeekArc("Find weaknesses: probe authentication, input handling and access control.",
                    "At least five documented findings, each with steps to reproduce and evidence."),
            WeekArc("Fix and verify: mitigate the most serious findings in code or configuration.",
                    "Patches or configuration changes for the top findings, with proof each is closed."),
            WeekArc("Report: rate the risk of each finding and write the remediation plan.",
                    "A professional report with risk ratings, a fix plan and a retest summary."),
        ),
        evidence='A GitHub repository holding the lab notes, each finding with its steps and evidence, the patches and the final report; the README lists the findings.',
    ),
    Seed(
        id="sec-api-hardening",
        track=T.CYBERSECURITY,
        title="Harden a REST API",
        brief=(
            "Take a small REST API and make it defensible: threat-model it, fix its authentication and "
            "input handling, remove hard-coded secrets and add monitoring."
        ),
        skills=("authentication and authorisation", "input validation", "secrets management", "dependency scanning", "logging"),
        arc=(
            WeekArc("Baseline: run the API, map its attack surface and record the starting risks.",
                    "A threat model and a prioritised list of the API's weaknesses."),
            WeekArc("Identity and input: strengthen authentication, authorisation and validation.",
                    "Fixed auth and validation flaws, each with a test that fails before the fix."),
            WeekArc("Operations: secrets handling, dependency scanning, logging and alerting.",
                    "No secrets in the repository, a dependency scan in CI and useful security logs."),
            WeekArc("Prove it: a security test suite and a hardening report.",
                    "An automated security test suite and a report of what changed and what risk remains."),
        ),
        evidence='A GitHub repository with the fixes, the security tests and a hardening report; the README summarises what changed and what risk remains.',
    ),
    Seed(
        id="sec-soc-monitoring",
        track=T.CYBERSECURITY,
        title="Security Monitoring and Incident Response Lab",
        brief=(
            "Build a small monitoring lab that collects logs from a few systems, write rules that detect "
            "suspicious behaviour, then investigate a simulated attack and write it up like a security analyst."
        ),
        skills=("log collection and analysis", "detection rules", "incident investigation", "timeline reconstruction", "incident reporting"),
        arc=(
            WeekArc("Build the lab: a few systems, log collection and a way to search the logs.",
                    "A working lab with logs from at least two sources searchable in one place, and a diagram of it."),
            WeekArc("Detect: write detection rules for common suspicious behaviour, such as repeated failed logins.",
                    "At least four detection rules, each with a test event that triggers it and a note on false positives."),
            WeekArc("Investigate: run a simulated attack and trace it through the logs.",
                    "Log evidence of the simulated attack and a reconstructed timeline of what happened."),
            WeekArc("Report: write the incident report and a response playbook.",
                    "An incident report with timeline, impact and root cause, and a short playbook for next time."),
        ),
        evidence='A GitHub repository with the detection rules, lab configuration and diagram; the README includes log excerpts or screenshots of the investigation and links the incident report.',
    ),
    # ------------------------------------------------------------------ networks & infrastructure
    Seed(
        id="net-branch-office",
        track=T.NETWORKS_INFRASTRUCTURE,
        title="Branch Office Network Design",
        brief=(
            "Design and simulate the network for a small branch office: addressing, segmentation, "
            "routing, basic security and a way to know when something breaks."
        ),
        skills=("IP addressing and subnetting", "VLANs and routing", "DHCP and DNS", "ACLs and firewalling", "documentation"),
        arc=(
            WeekArc("Requirements and design: what the office needs, an addressing plan and a topology.",
                    "A written requirements list, an addressing plan and a topology diagram."),
            WeekArc("Build the core: VLANs, inter-VLAN routing, DHCP and DNS in a simulator.",
                    "A working simulated network where devices in different VLANs get addresses and reach each other."),
            WeekArc("Secure it: access control lists or firewall rules, and guest access.",
                    "Documented security rules, tested to allow what should work and block what should not."),
            WeekArc("Operate it: monitoring, failure tests and a runbook.",
                    "A monitoring plan, evidence of at least two failure tests and an operations runbook."),
        ),
        evidence='A GitHub repository holding the exported simulator file, device configuration files, the topology diagram and notes; the README shows screenshots of the tests that were run.',
    ),
    Seed(
        id="net-services-lab",
        track=T.NETWORKS_INFRASTRUCTURE,
        title="Internal Services Lab",
        brief=(
            "Build a small lab of Linux servers that provide the services every company needs: name "
            "resolution, addressing, file sharing, remote access and monitoring."
        ),
        skills=("Linux administration", "DNS and DHCP", "VPN and remote access", "backup", "monitoring"),
        arc=(
            WeekArc("Build the lab: virtual machines, addressing and a base configuration.",
                    "Two or more networked machines with a documented base setup."),
            WeekArc("Core services: DNS, DHCP and a shared file service.",
                    "Working DNS, DHCP and file sharing, each with a short test showing it works."),
            WeekArc("Access and safety: VPN or secure remote access, and backups.",
                    "Remote access that works, and a backup that has actually been restored once."),
            WeekArc("Watch it: monitoring, alerting and documentation.",
                    "Monitoring with at least one alert firing on purpose, plus a runbook."),
        ),
        evidence='A GitHub repository with the configuration files, setup notes and a runbook; the README shows command output or screenshots proving each service works.',
    ),
    # ------------------------------------------------------------------ information systems
    Seed(
        id="is-leave-workflow",
        track=T.INFORMATION_SYSTEMS,
        title="Employee Leave and Approval Workflow",
        brief=(
            "Analyse how a company handles leave requests today, design a better process, and build the "
            "system that supports it, from requirements to a rollout plan."
        ),
        skills=("requirements analysis", "process modelling", "data modelling", "user acceptance testing", "change management"),
        arc=(
            WeekArc("Requirements: stakeholders, user stories and the current process.",
                    "A stakeholder list, user stories with acceptance criteria and a process map of how it works today."),
            WeekArc("Design: the target process, the data model and clickable prototypes.",
                    "A target process, an entity-relationship diagram and prototypes of the key screens."),
            WeekArc("Build: the core request-and-approve workflow and a simple report.",
                    "A working workflow where a request is submitted, approved or rejected, and reported on."),
            WeekArc("Prove and roll out: user acceptance tests, documentation and a rollout plan.",
                    "Test results against the acceptance criteria, user documentation and a rollout plan."),
        ),
        evidence='A GitHub repository with the requirements, process maps and diagrams as files, screenshots of the working system and the test results; the README indexes them.',
    ),
    Seed(
        id="is-inventory-dashboard",
        track=T.INFORMATION_SYSTEMS,
        title="Inventory and Reporting Dashboard",
        brief=(
            "Turn messy inventory spreadsheets into a reliable data model and a dashboard that lets a "
            "manager see stock levels, shortages and trends."
        ),
        skills=("data modelling", "data cleaning and ETL", "KPI design", "dashboarding", "data quality"),
        arc=(
            WeekArc("Understand the business: the questions managers ask and the data available.",
                    "A list of key questions and KPIs, and an inventory of the source data with its problems."),
            WeekArc("Model and load: a proper data model and a repeatable load from the raw files.",
                    "An ER diagram and a load script that turns the raw files into clean tables."),
            WeekArc("Report: the dashboard, KPIs and data-quality checks.",
                    "A dashboard answering the key questions, with data-quality checks that catch bad rows."),
            WeekArc("Hand over: validation with a stakeholder, documentation and next steps.",
                    "Stakeholder feedback recorded, a user guide and a short list of next improvements."),
        ),
        evidence='A GitHub repository with the data model diagram, load scripts and documentation, and screenshots of the dashboard in the README.',
    ),
    # ------------------------------------------------------------------ cloud / devops
    Seed(
        id="cloud-cicd-service",
        track=T.CLOUD_DEVOPS,
        title="CI/CD for a Web Service",
        brief=(
            "Take a small web service and give it a real delivery pipeline: containers, automated tests "
            "and builds, deployment to a cloud environment and monitoring."
        ),
        skills=("containers", "CI/CD pipelines", "cloud deployment", "observability", "rollback strategy"),
        arc=(
            WeekArc("Containerise: run the service in a container and with Docker Compose locally.",
                    "A Dockerfile and a compose file that start the service and its dependencies with one command."),
            WeekArc("Automate: a CI pipeline that tests the code and builds an image on every push.",
                    "A pipeline that runs tests, builds an image and fails clearly when something is wrong."),
            WeekArc("Deploy: push the image to a registry and deploy to a cloud or local cluster.",
                    "A deployed environment reachable by a URL, created by scripted or pipeline steps."),
            WeekArc("Operate: monitoring, a rollback plan and a runbook.",
                    "Dashboards or alerts for the service, a demonstrated rollback and a runbook."),
        ),
        evidence='A GitHub repository with the Dockerfile, pipeline configuration and runbook; the README links or shows screenshots of the pipeline run and the running service.',
    ),
    Seed(
        id="cloud-three-tier-iac",
        track=T.CLOUD_DEVOPS,
        title="Three-Tier Infrastructure as Code",
        brief=(
            "Describe a complete three-tier application environment (network, compute, database) as "
            "code, so it can be created, changed and destroyed repeatably and safely."
        ),
        skills=("infrastructure as code", "cloud networking", "IAM and least privilege", "secrets", "cost awareness"),
        arc=(
            WeekArc("Design: the architecture, the state strategy and the first resources.",
                    "An architecture diagram and code that creates the base network."),
            WeekArc("Network and compute: reusable modules for the network and application servers.",
                    "Reviewed modules that create the network and compute, with variables documented."),
            WeekArc("Data and security: the database, secrets and least-privilege access.",
                    "A database tier and access rules where each identity can do only what it needs."),
            WeekArc("Cost and resilience: tagging, monitoring, backup and safe teardown.",
                    "A cost estimate, a backup or recovery note and a clean, verified teardown."),
        ),
        evidence='A GitHub repository with the infrastructure code, architecture diagram and notes; the README includes plan or apply output as proof.',
    ),
)

_BY_ID = {s.id: s for s in SEEDS}

# Stage 1's only track. Those graduates get the software-engineering seeds.
_TRACK_ALIASES = {T.JUNIOR_DEV: T.SOFTWARE_ENGINEERING}

SUBTASK_PRINCIPLES = (
    "HOW TO SHAPE THE FIVE SUBTASKS. Each one must be doable in about one working day and "
    "reviewable on its own: it ends in something concrete a mentor can check (a link, a file, a "
    "test run, a screenshot, a short write-up). Order them so each builds on the one before. Give "
    "each a clear 'done when' in its description. Prefer real engineering habits (a README, a test, "
    "a commit history) over busywork, and keep the difficulty realistic for a recent graduate. "
    "IMPORTANT: the Mentor reviews a submitted GitHub repository by reading its file list and the start "
    "of its README - not the code itself. So every subtask must say what to put in the README (what was "
    "done, how to run or test it, and proof such as output or a screenshot) and what to commit, so the "
    "work can actually be seen and judged."
)


def seeds_for(track: TrackEnum) -> list[Seed]:
    track = _TRACK_ALIASES.get(track, track)
    return [s for s in SEEDS if s.track == track]


def get_seed(seed_id: str | None) -> Seed | None:
    return _BY_ID.get(seed_id) if seed_id else None


def seeds_prompt_block(track: TrackEnum) -> str:
    """The seeds a graduate's project can be based on, for the create_project prompt."""
    lines = [
        "PROJECT SEEDS for this graduate's track. Base their project on the seed that best fits their "
        "CV and interests, and ADAPT it: give it a specific name, and tune the scope and difficulty to "
        "their level. A seed is a starting point, not a script. Record your choice in seed_id."
    ]
    for s in seeds_for(track):
        lines.append(f"\n- {s.id}: {s.title}. {s.brief} Skills: {', '.join(s.skills)}.")
    return "\n".join(lines)


def week_arc_block(seed_id: str | None, week_number: int) -> str:
    """Where this week sits in the project's arc, for the plan_week prompt. Empty for a project with no seed."""
    seed = get_seed(seed_id)
    if seed is None:
        return ""
    if 1 <= week_number <= len(seed.arc):
        step = seed.arc[week_number - 1]
        return (
            f"PROJECT ARC ({seed.title}, week {week_number} of {len(seed.arc)}). "
            f"Focus this week: {step.focus} "
            f"By the end of the week this should exist: {step.deliverable} "
            f"Evidence the graduate submits for review: {seed.evidence} "
            "Shape the five subtasks so they build toward that, and name in each subtask what to submit."
        )
    return (
        f"PROJECT ARC ({seed.title}). The planned {len(seed.arc)}-week arc is complete. Extend the project "
        "in a sensible direction: harden it, add a meaningful feature, improve tests and documentation, "
        "and prepare something worth presenting - continuing the same thread of work. "
        f"Evidence the graduate submits for review: {seed.evidence}"
    )


def create_project_tool_for(track: TrackEnum) -> dict:
    """The create_project tool with an optional seed_id restricted to this track's seeds.
    The shared CREATE_PROJECT_TOOL is copied, never mutated."""
    tool = copy.deepcopy(CREATE_PROJECT_TOOL)
    tool["input_schema"]["properties"]["seed_id"] = {
        "type": "string",
        "enum": [s.id for s in seeds_for(track)],
        "description": "Which project seed you based this project on.",
    }
    return tool
