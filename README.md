# Virtual Work Environment (Venv)

An AI-powered work simulation platform for students and recent graduates. It analyzes a CV, evaluates the user's level through 10 questions, creates a personalized career path, and assigns one task at a time through three connected AI agents: Manager, Mentor, and HR.

## Requirements

- Docker Desktop
- Git
- An OpenAI API key (optional; the app uses demo responses without one)

## First-Time Setup

```bash
git clone https://github.com/Faisal-Alrashed1/Virtual-Work-Environment.git
cd Virtual-Work-Environment
cp .env.example .env
docker compose up --build
```

To enable real AI responses, open `.env` and add your key:

```env
OPENAI_API_KEY=your_key_here
```

The `.env` file is ignored by Git and will not be uploaded. Never place a real key in `.env.example` or in the source code.

When Docker displays `Ready`, open:

- Web app: http://localhost:3000
- API documentation: http://localhost:8000/docs

## Common Commands

```bash
# Start in the background
docker compose up -d

# Check service status
docker compose ps

# View live logs
docker compose logs -f

# Stop the project
docker compose down

# Rebuild after code changes
docker compose up -d --build
```

On macOS, Docker Desktop must be open and show `Engine running` before you run these commands.

## How to Try the Platform

1. Create an account and upload a PDF or DOCX CV (maximum 8 MB).
2. Answer the 10 level-assessment questions and describe your learning goal.
3. Generate your career path and start the task assigned by the Manager.
4. Ask the Mentor for guidance, submit your GitHub link, and discuss the result.
5. Review the independent Manager, Mentor, and HR evaluations, then continue to the next task.

## Technology

- `apps/web`: Next.js and React frontend.
- `apps/api`: FastAPI and Python backend, AI agents, and task lifecycle.
- `db`: PostgreSQL with pgvector, running in Docker.
- `infra`: Database initialization files.

## Run Tests

```bash
docker compose exec api sh -lc "PYTHONPATH=/app pytest -q"
```

## Troubleshooting

- `docker: command not found`: Open Docker Desktop, then reopen Terminal.
- `connection refused`: Run `docker compose ps` and confirm that `web`, `api`, and `db` are running.
- `Load failed`: Run `docker compose logs api` and verify the values in `.env`.
- After changing the API key, run `docker compose up -d --force-recreate api`.

## Security

Local environment files, uploaded CVs, database files, build output, dependencies, and logs are excluded from Git. Do not commit real credentials or sensitive production data.
