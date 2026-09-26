"""
Real invitation emails (docs/STAGE3_COMPANY_RAG.md). Plain smtplib —
no new dependency — works with any SMTP provider (Gmail, SendGrid,
Mailgun, AWS SES, Postmark's SMTP relay, or a real mail server).

Optional by design: if SMTP_HOST isn't configured, send_invitation_email
raises EmailNotConfigured, and every caller (routers/company.py) treats
that as a soft no-op rather than a request failure — an invitation
always exists and is findable via GET /invitations/mine (matched by
email) whether or not an email actually goes out. The same holds for a
real SMTP error (server down, bad credentials): the invitation itself
must never fail to save just because the email couldn't be sent.
"""
import smtplib
import ssl
from email.message import EmailMessage

from app.config import settings


class EmailNotConfigured(Exception):
    """SMTP_HOST isn't set. Callers catch this specifically and continue
    — see routers/company.py's create_invitation."""


def _invitation_message(
    *, to_email: str, company_name: str, job_title: str, project_title: str | None, accept_url: str
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"{company_name} invited you to work under their account on Venv"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    what = f'the "{project_title}" project' if project_title else "the ordinary Venv track"
    msg.set_content(
        f"{company_name} has invited you to work under their account on Venv, "
        f"as a {job_title}, on {what}.\n\n"
        f"See the full details and respond here:\n{accept_url}\n\n"
        f"You'll be shown exactly what {company_name} will — and won't — be able "
        f"to see about your work before you have to decide anything."
    )
    msg.add_alternative(
        f"""\
<html><body style="font-family: -apple-system, sans-serif; color: #1a1a1a; line-height: 1.5;">
  <p><strong>{company_name}</strong> has invited you to work under their account
  on Venv, as a <strong>{job_title}</strong>, on {what}.</p>
  <p>
    <a href="{accept_url}"
       style="display:inline-block; padding:10px 18px; background:#0f766e;
              color:#ffffff; text-decoration:none; border-radius:6px; font-weight:500;">
      View invitation
    </a>
  </p>
  <p style="color:#666666; font-size:13px;">
    You'll be shown exactly what {company_name} will — and won't — be able to
    see about your work before you have to decide anything.
  </p>
</body></html>
""",
        subtype="html",
    )
    return msg


def send_invitation_email(
    *, to_email: str, company_name: str, job_title: str, project_title: str | None = None
) -> None:
    """Sends the actual invitation email over SMTP. Raises
    EmailNotConfigured if SMTP_HOST is blank; raises smtplib.SMTPException
    or OSError on a real send failure (bad credentials, server
    unreachable) — both are the caller's to catch and swallow, never a
    reason to fail the invitation itself."""
    if not settings.smtp_host:
        raise EmailNotConfigured("SMTP_HOST is not set — no email was sent.")

    accept_url = f"{settings.frontend_base_url.rstrip('/')}/invitations"
    msg = _invitation_message(
        to_email=to_email,
        company_name=company_name,
        job_title=job_title,
        project_title=project_title,
        accept_url=accept_url,
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
