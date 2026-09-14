# Integration Points Documentation

## 1. Frontend <-> Backend API
- Base URL: `http://localhost:8000/api`
- Bearer Auth Header: `Authorization: Bearer <JWT_TOKEN>`
- Endpoints:
  - Auth: `/api/auth/register`, `/api/auth/login`, `/api/me`
  - Intake: `/api/intake/cv`, `/api/intake/manual-cv`, `/api/intake/chat`, `/api/intake/confirm`
  - Workspace: `/api/project/join`, `/api/project/start`, `/api/workspace`
  - Tasks & Submissions: `/api/tasks/{task_id}/status`, `/api/tasks/{task_id}/submit`
  - Company & Recruiter: `/api/organizations`, `/api/campaigns`, `/api/company/*`

## 2. Agents <-> Backend Agent Gateway
- All AI Agents interact with backend domain models via `app.api.agent_gateway.AgentGateway`.
- No agent accesses the database directly.
