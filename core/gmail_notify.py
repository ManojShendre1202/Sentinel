"""
Sends a failure-notification email via Gmail API. Requires gmail_token.json
(run `python manage.py gmail_auth_setup` once first).
"""
import base64
from email.mime.text import MIMEText

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _get_credentials() -> Credentials:
    if not settings.GMAIL_TOKEN_PATH.exists():
        raise RuntimeError("gmail_token.json not found — run `python manage.py gmail_auth_setup` first.")

    creds = Credentials.from_authorized_user_file(str(settings.GMAIL_TOKEN_PATH))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        settings.GMAIL_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def send_failure_email(agent_run) -> None:
    subject = f"Sentinel: Graph 1 run #{agent_run.pk} failed"
    body = (
        f"Trigger: {agent_run.trigger}\n"
        f"Started: {agent_run.started_at}\n"
        f"Failed: {agent_run.finished_at}\n\n"
        f"Errors:\n{agent_run.errors}\n\n"
        f"To resume from the last completed step:\n"
        f"python manage.py weekly_discovery_job --resume {agent_run.pk}"
    )

    message = MIMEText(body)
    message["to"] = settings.GMAIL_NOTIFY_ADDRESS
    message["from"] = settings.GMAIL_NOTIFY_ADDRESS
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service = build("gmail", "v1", credentials=_get_credentials())
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
