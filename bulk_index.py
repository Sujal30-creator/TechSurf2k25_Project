import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Your live Vercel API endpoint for indexing
YOUR_API_ENDPOINT = os.getenv("VERCEL_URL") + "/index" 
# Contentstack credentials
CS_API_KEY = os.getenv("CONTENTSTACK_API_KEY")
CS_MANAGEMENT_TOKEN = os.getenv("CONTENTSTACK_MANAGEMENT_TOKEN")
# The UID of the content type you want to index
CONTENT_TYPE_UID = "searchable_article" # <--- CHANGE THIS

# --- Main Script ---

def fetch_all_entries():
    """Fetches all entries of a specific content type from Contentstack."""
    print(f"Fetching all entries for content type: {CONTENT_TYPE_UID}...")
    
    # Construct the URL for the Contentstack Management API
    url = f"https://eu-api.contentstack.com/v3/content_types/{CONTENT_TYPE_UID}/entries?branch=main"
    
    headers = {
        "api_key": CS_API_KEY,
        "authorization": CS_MANAGEMENT_TOKEN,
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status() # Will raise an error for bad responses
    
    print(f"Found {len(response.json()['entries'])} entries.")
    return response.json()["entries"]

def index_entry(entry):
    """Sends a single entry to our own /index endpoint."""
    title = entry.get("title", "")
    print(f"  -> Indexing '{title}'...")

    # Construct the webhook payload our API expects
    payload = {
        "module": "entry",
        "event": "publish",
        "data": {
            "entry": {
                "uid": entry.get("uid"),
                "title": title,
                "locale": entry.get("locale"),
                "content_type": {
                    "uid": CONTENT_TYPE_UID
                }
            }
        }
    }
    
    # Make the POST request to our own API
    response = requests.post(YOUR_API_ENDPOINT, json=payload)
    
    if response.status_code == 200:
        print(f"     SUCCESS: {response.json().get('vector_id')}")
    else:
        print(f"     ERROR: {response.status_code} - {response.text}")

# --- Run the process ---
if __name__ == "__main__":
    try:
        all_entries = fetch_all_entries()
        for entry in all_entries:
            index_entry(entry)
            time.sleep(1) # Wait 1 second between requests to not overload the server
        print("\nBulk indexing complete!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")