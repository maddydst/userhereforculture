import base64
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = Path("token.pickle")
CREDS_PATH = Path("credentials.json")


def get_gmail_service():
    creds = None

    # Sur Railway : token encodé en base64 dans GMAIL_TOKEN
    env_token = os.environ.get("GMAIL_TOKEN", "")
    if env_token and not TOKEN_PATH.exists():
        TOKEN_PATH.write_bytes(base64.b64decode(env_token))

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)
        else:
            if not CREDS_PATH.exists():
                raise FileNotFoundError(
                    "credentials.json manquant."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)
