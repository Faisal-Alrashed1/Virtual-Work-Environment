# Career Coach Agent

## Overview

The Career Coach Agent provides personalized career guidance for trainees in Venv.

It uses the trainee's track, employee profile, skills, strengths, growth areas, and recent reviews to provide practical career advice.

## Main Responsibilities

- Career planning
- Skill-gap guidance
- Resume improvement
- Portfolio development
- Interview preparation
- Short-term career goals

The Career Coach does not replace the Manager or Mentor agents.

## Main Files

### Agent Logic

`backend/app/agents/coach.py`

Contains:

- `SYSTEM_PROMPT`
- `build_context()`
- `build_career_profile()`
- `generate_reply()`
- `generate_career_plan()`

### Meeting Integration

`backend/app/agents/meeting.py`

The meeting system routes Career Coach conversations to the dedicated Coach Agent logic.

## Flow

User Request

↓  

`POST /meeting/career_coach`

↓

`meeting.send_message()`

↓

Career Coach detected

↓

`coach.generate_reply()`

or

`coach.generate_career_plan()`

↓

Career context is built from trainee data

↓

LLM generates the response

↓

Response is stored as a `ChatMessage`

## Career Context

The Coach can use:

- Confirmed career track
- Current skills
- Strengths
- Growth areas
- Employee File summary
- Recent performance reviews

## Career Plan

When the user requests a career plan, the Coach generates a plan containing:

- Current position
- Important skill gaps
- Three short-term goals
- Concrete actions
- Recommended next career step

## API Example

Endpoint:

`POST /meeting/{agent}`

Agent:

`career_coach`

Example request:

```json
{
  "content": "Create a career plan for me."
}
