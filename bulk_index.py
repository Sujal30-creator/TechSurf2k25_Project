import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
YOUR_API_ENDPOINT = os.getenv("VERCEL_URL") + "/index" 
CS_API_KEY = os.getenv("CONTENTSTACK_API_KEY")
CS_MANAGEMENT_TOKEN = os.getenv("CONTENTSTACK_MANAGEMENT_TOKEN")
CONTENT_TYPE_UID = "searchable_article"

# --- Main Script ---

def fetch_all_entries():
    """Fetches all entries of a specific content type from Contentstack."""
    print(f"Fetching all entries for content type: {CONTENT_TYPE_UID}...")
    
    url = f"https://eu-api.contentstack.com/v3/content_types/{CONTENT_TYPE_UID}/entries"
    headers = {
        "api_key": CS_API_KEY,
        "authorization": CS_MANAGEMENT_TOKEN,
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    entries = response.json().get('entries', [])
    print(f"Found {len(entries)} entries.")
    return entries

def index_entry(entry):
    """Sends a single entry to our own /index endpoint, formatted like a webhook."""
    title = entry.get("title", "")
    print(f"  -> Indexing '{title}'...")

    # We format the payload exactly as a Contentstack webhook would
    payload = {
        "module": "entry",
        "event": "publish",
        "data": {
            "entry": {
                "uid": entry.get("uid"),
                "locale": entry.get("locale"),
            },
             "content_type": {
                "uid": CONTENT_TYPE_UID
            }
        }
    }
    
    response = requests.post(YOUR_API_ENDPOINT, json=payload)
    
    if response.status_code == 200:
        print(f"     SUCCESS: {response.json().get('vector_id')}")
    else:
        print(f"     ERROR: {response.status_code} - {response.text}")

# --- Run the process ---
if __name__ == "__main__":
    try:
        all_entries = fetch_all_entries()
        if not all_entries:
            print("No entries found to index.")
        else:
            for entry in all_entries:
                index_entry(entry)
                time.sleep(1) # Prevent rate-limiting
            print("\nBulk re-indexing complete!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")