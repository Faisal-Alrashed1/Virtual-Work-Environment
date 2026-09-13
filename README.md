# Virtual Work Environment

An AI-powered workplace simulation for students and recent graduates. The user joins as a Junior Web Developer and works with three focused AI agents:

- **Senior:** supervises the Junior, splits the project into tasks, reviews code, and gives progressive hints.
- **Manager:** introduces the project and evaluates weekly technical performance from the Senior's report.
- **HR:** evaluates professional behavior and produces the final weekly evaluation.

Phase 1 focuses on Web Development. Difficulty adapts to demonstrated weekly performance. Companies can also create controlled candidate environments using synthetic or anonymized knowledge.

## Structure

```text
apps/api/              Python + FastAPI backend
  app/api/             HTTP endpoints
  app/core/            configuration, database, security
  app/models/          database tables
  app/schemas/         validated requests
  app/services/        AI, GitHub, CV, tasks, reports
  tests/               backend tests
apps/web/              Next.js frontend
  app/                 pages and styles
  components/          reusable UI
  lib/                 API client
run.py                 starts both services
```

## Requirements

- Python 3.11+
- Node.js 20+
- Git
- DeepSeek API key (optional; demo responses work without it)

Docker is not required.

## First setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r apps/api/requirements.txt
cd apps/web && npm install && cd ../..
cp .env.example .env
```

DeepSeek is the platform's only AI provider. Put the key only in `.env`:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

Create a private JWT secret using `python -c "import secrets; print(secrets.token_urlsafe(48))"` and put it in `JWT_SECRET`. Never place secrets in source code or `.env.example`.

## Run everything

```bash
python3 run.py
```

- Platform: http://localhost:3000
- API documentation: http://localhost:8000/docs

Press `Control+C` to stop both services.

## Run separately

Backend terminal:

```bash
source .venv/bin/activate
cd apps/api
PYTHONPATH=. python -m uvicorn app.main:app --reload --port 8000
```

Frontend terminal:

```bash
cd apps/web
npm run dev
```

## Verify

```bash
source .venv/bin/activate
PYTHONPATH=apps/api pytest -q apps/api/tests
cd apps/web && npm run build
```

## Database and security

The MVP uses the local `venv.db` SQLite database, so no database server is needed. SQLAlchemy keeps the data layer replaceable if PostgreSQL is required later.

- Never commit `.env`, `venv.db`, uploaded CVs, real company data, or API keys.
- Company knowledge must be synthetic or anonymized.
- User and company resources are checked against the authenticated owner.
- AI evaluations must cite evidence and never make the final hiring decision.
