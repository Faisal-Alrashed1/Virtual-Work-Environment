# Virtual Work Environment (Venv) - Architecture Documentation

## Overview
Virtual Work Environment (Venv) is an AI-powered workplace simulator designed for entry-level developers (B2C) and hiring companies (B2B).

## Core Architecture: Modular Monolith

```
apps/
├── api/
│   └── app/
│       ├── api/               # Domain-driven HTTP Route Handlers
│       │   ├── routes/
│       │   │   ├── auth.py      # Authentication & User Profile
│       │   │   ├── intake.py    # Onboarding & CV Diagnostic
│       │   │   ├── workspace.py # Project & Weekly Cycles
│       │   │   ├── agents.py    # Inter-Agent Chat Sync
│       │   │   ├── tasks.py     # Submissions & Discussions
│       │   │   └── recruiter.py # B2B Organization & Campaigns
│       │   └── dependencies.py  # Dependency Injection & Guards
│       ├── core/                # DB, Config, Security & JWT
│       ├── models/              # SQLAlchemy Data Models
│       ├── schemas/             # Pydantic Request/Response DTOs
│       └── services/            # Core Domain Logic
│           ├── agents/          # AI Agent Personas (Manager, Senior, HR, CV)
│           ├── ai.py            # LLM Provider Gateway
│           ├── onboarding.py    # Diagnostic Engine
│           ├── orchestrator.py  # Cycle & Evaluation Orchestration
│           └── documents.py     # File Processing & Verification
└── web/                         # Next.js Arabic RTL Frontend
```

## AI Agent Ecosystem

| Agent Persona | Role & Responsibilities |
|---|---|
| **Manager** | Project Kickoff, Scope Definition, Technical Performance Evaluation |
| **Senior (Technical Reviewer)** | Daily Task Guidance, Code Review, Discussion & Mentorship |
| **HR** | Behavioral Monitoring, Communication Rating, Weekly Evaluation |
| **CV Analyzer / Career** | Resume Skill Extraction, Diagnostic Questioning, Learning Path Generation |

## Data Flows & Execution Pipeline
1. **Learner Onboarding**: CV Parsing / Manual Entry -> 10 Diagnostic Questions -> Career Path Generation.
2. **Weekly Sprint Cycle**: 5 Micro-Tasks -> Code Submission / GitHub Pinning -> Senior Review -> Discussion -> Task Closure.
3. **Weekly Evaluation**: Senior Tech Report -> Manager Grade -> HR Behavior Score -> Dynamic Difficulty Scaling.
4. **Recruiter Track**: Synthetic Knowledge Base Indexing -> Custom Task Definition -> Approval Pipeline -> Final Hiring Decision.
