"""
Run this script ONCE on your local machine to generate YouTube OAuth credentials.

Steps:
  1. Download client_secret.json from Google Cloud Console (OAuth 2.0 Desktop app)
     and place it in the scripts/ folder.
  2. Run: python scripts/youtube_auth_setup.py
  3. A browser window opens — log in as the YouTube channel owner and allow access.
  4. Copy the printed values to GitHub Secrets:
       YOUTUBE_CLIENT_ID
       YOUTUBE_CLIENT_SECRET
       YOUTUBE_REFRESH_TOKEN

Do NOT commit client_secret.json or the generated token to git.
"""
import json
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "client_secret.json")


def main() -> None:
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(
            f"ERROR: {CLIENT_SECRET_FILE} not found.\n"
            "Download it from Google Cloud Console:\n"
            "  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON\n"
            "Save it as scripts/client_secret.json and re-run this script."
        )
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Run: pip install google-auth-oauthlib")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=8080, prompt="consent")

    print("\n" + "=" * 60)
    print("SUCCESS — copy these values to GitHub Secrets:")
    print("=" * 60)
    print(f"YOUTUBE_CLIENT_ID:     {credentials.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET: {credentials.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN: {credentials.refresh_token}")
    print("=" * 60)
    print("\nAlso get your GEMINI_API_KEY free from:")
    print("  https://aistudio.google.com/apikey")


if __name__ == "__main__":
    main()
