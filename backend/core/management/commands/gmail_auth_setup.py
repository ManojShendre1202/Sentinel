"""
One-time interactive Gmail OAuth setup. Opens a browser for you to approve
access, then caches a refresh token at settings.GMAIL_TOKEN_PATH (gitignored).
Run once: python manage.py gmail_auth_setup
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class Command(BaseCommand):
    help = "One-time interactive Gmail OAuth setup for failure-notification emails."

    def handle(self, *args, **options):
        client_config = {
            "installed": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

        settings.GMAIL_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        self.stdout.write(f"Saved refresh token to {settings.GMAIL_TOKEN_PATH}")
