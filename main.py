import os
import requests
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Environment variables
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_ISSUE_KEY = os.getenv("JIRA_ISSUE_KEY")
ATTACHMENT_DOWNLOAD_PATH = "./tmp"  # Always use ./tmp for local saving

@app.post("/")
async def download_attachments():
    # Ensure variables are present
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_ISSUE_KEY]):
        return {"error": "Missing required environment variables."}

    # Ensure ./tmp exists
    os.makedirs(ATTACHMENT_DOWNLOAD_PATH, exist_ok=True)

    # Jira API auth and issue URL
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    issue_url = f"{JIRA_BASE_URL}/rest/api/3/issue/{JIRA_ISSUE_KEY}"

    # Fetch issue
    response = requests.get(issue_url, auth=auth)
    if response.status_code != 200:
        return {"error": f"Failed to fetch issue. Status {response.status_code}", "details": response.text}

    issue_data = response.json()
    attachments = issue_data["fields"].get("attachment", [])
    results = []

    # Download each attachment to ./tmp
    for attachment in attachments:
        filename = attachment["filename"]
        content_url = attachment["content"]
        filepath = os.path.join(ATTACHMENT_DOWNLOAD_PATH, filename)

        try:
            file_response = requests.get(content_url, auth=auth)
            if file_response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(file_response.content)
                results.append(f"Saved to: {filepath}")
            else:
                results.append(f"Failed to download {filename}: HTTP {file_response.status_code}")
        except Exception as e:
            results.append(f"Error downloading {filename}: {str(e)}")

    return {"results": results}
