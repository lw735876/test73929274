#!/usr/bin/env python3
import logging
import os
import requests
from mcp.server.fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load Jira credentials from environment variables (passed from jira.json)
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY = os.getenv("PROJECT_KEY")  
ISSUE_KEY = os.getenv("ISSUE_KEY")  
ATTACHMENT_DOWNLOAD_PATH = "./tmp"  

# Create MCP server
mcp = FastMCP("jira-mcp-server")

@mcp.tool()
def get_epic_name_field_id() -> str:
    """Retrieve the custom field ID for the Epic Name field in Jira."""
    url = f"{JIRA_URL}/rest/api/3/field"
    auth = (JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        fields = response.json()
        
        for field in fields:
            if field.get("name") == "Epic Name":
                return field["id"]
        
        return "customfield_10011"  # Fallback if not found
        
    except requests.RequestException as e:
        logger.error(f"Error fetching Epic Name field ID: {str(e)}")

@mcp.tool()
def get_project_info() -> dict:
    """Get information about the configured project.
    
    Returns:
        Dictionary containing project details
    """
    url = f"{JIRA_URL}/rest/api/3/project/{PROJECT_KEY}"
    auth = (JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        project = response.json()
        
        return {
            "project_key": PROJECT_KEY,
            "project_name": project.get("name"),
            "project_id": project.get("id"),
            "project_type": project.get("projectTypeKey"),
            "description": project.get("description", "No description available")
        }
        
    except requests.RequestException as e:
        logger.error(f"Error fetching project info for {PROJECT_KEY}: {str(e)}")

@mcp.tool()
def download_attachments(issue_key: str = None, filenames: list = None) -> dict:
    """Download attachments from a specified Jira issue and save them locally.
    
    Args:
        issue_key: The key of the Jira issue. If not provided, uses ISSUE_KEY from environment.
        filenames: List of specific filenames to download. If None or empty, downloads all attachments.
    
    Returns:
        Dictionary containing list of downloaded file paths
    """
    # Use environment issue key if none provided
    if not issue_key:
        if not ISSUE_KEY:
            logger.error("No issue_key provided and ISSUE_KEY environment variable not set")
        issue_key = ISSUE_KEY
        logger.info(f"No issue_key provided, using environment ISSUE_KEY: {issue_key}")
    
    # Validate that issue belongs to the configured project
    if not issue_key.startswith(f"{PROJECT_KEY}-"):
        logger.warning(f"Issue key {issue_key} does not belong to configured project {PROJECT_KEY}")
    
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    auth = (JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        issue = response.json()
        
        attachments = issue.get("fields", {}).get("attachment", [])
        saved_files = []
        not_found_files = []
        
        # Create attachment download directory if it doesn't exist
        os.makedirs(ATTACHMENT_DOWNLOAD_PATH, exist_ok=True)
        
        if not attachments:
            logger.info(f"No attachments found for issue {issue_key}")
            return {"downloaded_files": [], "message": f"No attachments found for issue {issue_key}"}
        
        # If filenames specified, filter attachments
        if filenames:
            available_files = [att["filename"] for att in attachments]
            logger.info(f"Requested files: {filenames}")
            logger.info(f"Available files: {available_files}")
            
            for filename in filenames:
                # Find attachment with matching filename
                matching_attachment = None
                for attachment in attachments:
                    if attachment["filename"] == filename:
                        matching_attachment = attachment
                        break
                
                if matching_attachment:
                    file_url = matching_attachment["content"]
                    file_name = matching_attachment["filename"]
                    
                    file_response = requests.get(file_url, auth=auth)
                    file_response.raise_for_status()
                    
                    file_path = os.path.join(ATTACHMENT_DOWNLOAD_PATH, file_name)
                    with open(file_path, "wb") as f:
                        f.write(file_response.content)
                    
                    saved_files.append(file_path)
                    logger.debug(f"Downloaded attachment: {file_path}")
                else:
                    not_found_files.append(filename)
                    logger.warning(f"File '{filename}' not found in attachments")
        else:
            # Download all attachments (original behavior)
            for attachment in attachments:
                file_url = attachment["content"]
                file_name = attachment["filename"]
                
                file_response = requests.get(file_url, auth=auth)
                file_response.raise_for_status()
                
                file_path = os.path.join(ATTACHMENT_DOWNLOAD_PATH, file_name)
                with open(file_path, "wb") as f:
                    f.write(file_response.content)
                
                saved_files.append(file_path)
                logger.debug(f"Downloaded attachment: {file_path}")
        
        # Prepare response message
        if filenames:
            if not_found_files:
                message = f"Downloaded {len(saved_files)} of {len(filenames)} requested files from issue {issue_key}. Not found: {not_found_files}"
            else:
                message = f"Successfully downloaded all {len(saved_files)} requested files from issue {issue_key}"
        else:
            message = f"Successfully downloaded {len(saved_files)} attachments from issue {issue_key}"
        
        return {
            "downloaded_files": saved_files,
            "not_found_files": not_found_files,
            "message": message,
            "issue_key": issue_key,
            "project_key": PROJECT_KEY
        }
        
    except requests.RequestException as e:
        logger.error(f"Error downloading attachments for {issue_key}: {str(e)}")

@mcp.tool()
def upload_attachment(filename: str, issue_key: str = None) -> dict:
    """Upload a local file from the tmp directory to a specified Jira issue.
    
    Args:
        filename: The name of the file in the tmp directory
        issue_key: The key of the Jira issue. If not provided, uses ISSUE_KEY from environment.
    
    Returns:
        Dictionary containing uploaded filename
    """
    # Use environment issue key if none provided
    if not issue_key:
        if not ISSUE_KEY:
            logger.error("No issue_key provided and ISSUE_KEY environment variable not set")
        issue_key = ISSUE_KEY
        logger.info(f"No issue_key provided, using environment ISSUE_KEY: {issue_key}")
    
    # Validate that issue belongs to the configured project
    if not issue_key.startswith(f"{PROJECT_KEY}-"):
        logger.warning(f"Issue key {issue_key} does not belong to configured project {PROJECT_KEY}")
    
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/attachments"
    auth = (JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"X-Atlassian-Token": "no-check"}
    
    file_path = os.path.join(ATTACHMENT_DOWNLOAD_PATH, filename)
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} not found")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f)}
            response = requests.post(url, auth=auth, headers=headers, files=files)
            response.raise_for_status()
            
        logger.debug(f"Uploaded attachment: {filename} to {issue_key}")
        return {
            "uploaded_file": filename,
            "message": f"Successfully uploaded {filename} to issue {issue_key}",
            "issue_key": issue_key,
            "project_key": PROJECT_KEY
        }
        
    except requests.RequestException as e:
        logger.error(f"Error uploading {filename} to {issue_key}: {str(e)}")

@mcp.tool()
def list_tmp_files() -> dict:
    """List all files in the attachment download directory.
    
    Returns:
        Dictionary containing list of files in attachment download directory
    """
    if not os.path.exists(ATTACHMENT_DOWNLOAD_PATH):
        return {"files": [], "message": f"{ATTACHMENT_DOWNLOAD_PATH} directory does not exist"}
    
    try:
        files = [f for f in os.listdir(ATTACHMENT_DOWNLOAD_PATH) if os.path.isfile(os.path.join(ATTACHMENT_DOWNLOAD_PATH, f))]
        return {
            "files": files,
            "count": len(files),
            "message": f"Found {len(files)} files in {ATTACHMENT_DOWNLOAD_PATH} directory"
        }
    except Exception as e:
        logger.error(f"Error listing files in {ATTACHMENT_DOWNLOAD_PATH}: {str(e)}")

@mcp.tool()
def add_comment(comment_text: str, issue_key: str = None) -> dict:
    """Add a comment to a specified Jira issue.
    
    Args:
        comment_text: The text content of the comment to add
        issue_key: The key of the Jira issue. If not provided, uses ISSUE_KEY from environment.
    
    Returns:
        Dictionary containing comment details and success message
    """
    # Use environment issue key if none provided
    if not issue_key:
        if not ISSUE_KEY:
            logger.error("No issue_key provided and ISSUE_KEY environment variable not set")
        issue_key = ISSUE_KEY
        logger.info(f"No issue_key provided, using environment ISSUE_KEY: {issue_key}")
    
    # Validate that issue belongs to the configured project
    if not issue_key.startswith(f"{PROJECT_KEY}-"):
        logger.warning(f"Issue key {issue_key} does not belong to configured project {PROJECT_KEY}")
    
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    auth = (JIRA_USERNAME, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    # Prepare comment data
    comment_data = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": comment_text
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, auth=auth, headers=headers, json=comment_data)
        response.raise_for_status()
        comment = response.json()
        
        logger.debug(f"Added comment to issue {issue_key}: {comment_text[:50]}...")
        return {
            "comment_id": comment.get("id"),
            "comment_text": comment_text,
            "message": f"Successfully added comment to issue {issue_key}",
            "issue_key": issue_key,
            "project_key": PROJECT_KEY,
            "created": comment.get("created"),
            "author": comment.get("author", {}).get("displayName")
        }
        
    except requests.RequestException as e:
        logger.error(f"Error adding comment to {issue_key}: {str(e)}")

def main():
    """Entry point for the MCP server."""
    import sys
    
    # Check if running with stdio transport (default)
    if len(sys.argv) > 1 and sys.argv[1] in ["sse", "stdio"]:
        transport = sys.argv[1]
    else:
        # For Render deployment, default to sse instead of stdio
        transport = "sse" if os.getenv("PORT") else "stdio"
    
    logger.info(f"Starting Jira MCP server with {transport} transport")
    logger.info(f"Jira URL: {JIRA_URL}")
    logger.info(f"Username: {JIRA_USERNAME}")
    logger.info(f"Project Key: {PROJECT_KEY}")
    
    # Minimal fix for Render deployment
    if transport == "sse" and os.getenv("PORT"):
        import uvicorn
        from fastapi import FastAPI
        
        port = int(os.getenv("PORT", 8000))
        app = FastAPI()
        
        @app.get("/")
        def root():
            return {"message": "Jira MCP Server", "status": "running"}
        
        uvicorn.run(main, host="0.0.0.0", port=port)
    else:
        mcp.run(transport=transport)

if __name__ == "__main__":
    main()
