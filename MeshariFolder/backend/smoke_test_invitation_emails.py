"""
Smoke test for real invitation emails (docs/STAGE3_COMPANY_RAG.md,
app/email.py). Two things verified: the invitation endpoint degrades
gracefully with no SMTP configured, or on a real send failure
(email_sent False either way, invitation still created — never a
request failure) — and, the important one, that an actual local SMTP
server (aiosmtpd) genuinely receives a correctly-addressed,
correctly-worded email when SMTP *is* configured. That last part is not
mocked: a real SMTP connection, a real DATA command, a real message body
checked for the right sender, recipient, and content.

Run: python smoke_test_invitation_emails.py
"""
import os
import time
from unittest.mock import patch

os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "sqlite:///./smoke_test_invitation_emails.db"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "not-used-no-llm-calls-in-this-test")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
import app.email as email_mod  # noqa: E402

client = TestClient(app)
client.__enter__()


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, label


def login(email):
    r = client.post("/auth/login", data={"username": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- setup: a company + job title ---
client.post(
    "/company/register",
    json={
        "email": "admin@mailco.com",
        "password": "hunter2pass",
        "full_name": "Admin",
        "company_name": "MailCo",
    },
)
admin_headers = login("admin@mailco.com")
r = client.post("/company/job-titles", json={"title": "Data Analyst"}, headers=admin_headers)
job_title_id = r.json()["id"]


# --- 1. no SMTP configured: invitation still creates fine, email_sent is honestly False ---
check("SMTP_HOST starts blank in this test environment", email_mod.settings.smtp_host == "")
r = client.post(
    f"/company/job-titles/{job_title_id}/invitations",
    json={"invited_email": "nosend@example.com"},
    headers=admin_headers,
)
check("invitation created even with no SMTP configured -> 201", r.status_code == 201)
check("email_sent is honestly False", r.json()["email_sent"] is False)

r = client.get("/company/invitations", headers=admin_headers)
check(
    "the list endpoint reports email_sent honestly too",
    any(
        i["invited_email"] == "nosend@example.com" and i["email_sent"] is False
        for i in r.json()
    ),
)

# --- 2. a real send failure never blocks the invitation either ---
with patch("app.routers.company.send_invitation_email", side_effect=OSError("connection refused")):
    r = client.post(
        f"/company/job-titles/{job_title_id}/invitations",
        json={"invited_email": "sendfails@example.com"},
        headers=admin_headers,
    )
check("invitation still created even when the send raises -> 201", r.status_code == 201)
check("email_sent is False after a real send failure", r.json()["email_sent"] is False)


# --- 3. the real thing: an actual local SMTP server genuinely receives it ---
from aiosmtpd.controller import Controller  # noqa: E402

received = []


class _CaptureHandler:
    async def handle_DATA(self, server, session, envelope):
        received.append(
            {
                "mail_from": envelope.mail_from,
                "rcpt_tos": envelope.rcpt_tos,
                "content": envelope.content.decode("utf8", errors="replace"),
            }
        )
        return "250 Message accepted for delivery"


controller = Controller(_CaptureHandler(), hostname="127.0.0.1", port=1026)
controller.start()
time.sleep(0.3)

with (
    patch.object(email_mod.settings, "smtp_host", "127.0.0.1"),
    patch.object(email_mod.settings, "smtp_port", 1026),
    patch.object(email_mod.settings, "smtp_use_tls", False),
    patch.object(email_mod.settings, "frontend_base_url", "https://app.venv.dev"),
):
    r = client.post(
        f"/company/job-titles/{job_title_id}/invitations",
        json={"invited_email": "realsend@example.com"},
        headers=admin_headers,
    )

time.sleep(0.3)
controller.stop()

check("invitation with real SMTP configured -> 201", r.status_code == 201)
check("email_sent is honestly True this time", r.json()["email_sent"] is True)
check("the local SMTP server actually received exactly one message", len(received) == 1)

msg = received[0] if received else {}
check("envelope From matches SMTP_FROM_EMAIL", msg.get("mail_from") == email_mod.settings.smtp_from_email)
check("envelope To matches the invited email", msg.get("rcpt_tos") == ["realsend@example.com"])
check("body names the company", "MailCo" in msg.get("content", ""))
check("body names the job title", "Data Analyst" in msg.get("content", ""))
check(
    "body links to the frontend's /invitations page",
    "https://app.venv.dev/invitations" in msg.get("content", ""),
)
check(
    "body has both a plain-text and an HTML part (multipart)",
    "text/plain" in msg.get("content", "") and "text/html" in msg.get("content", ""),
)

print("\nAll invitation-email smoke checks passed.")
