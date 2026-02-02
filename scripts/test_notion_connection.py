"""
Test script to verify Notion API connection.
Run: python scripts/test_notion_connection.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_VERSION = "2022-06-28"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

def test_connection():
    """Test basic API connection by searching for all pages we have access to."""
    
    print("=" * 60)
    print("🔍 Testing Notion API Connection...")
    print("=" * 60)
    
    if not NOTION_API_KEY:
        print("❌ ERROR: NOTION_API_KEY not found in .env file")
        return False
    
    print(f"✓ API Key found (starts with: {NOTION_API_KEY[:10]}...)")
    
    # Search for all pages the integration has access to
    url = "https://api.notion.com/v1/search"
    
    payload = {
        "filter": {
            "property": "object",
            "value": "page"
        },
        "page_size": 100
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            print(f"\n✅ CONNECTION SUCCESSFUL!")
            print(f"📄 Found {len(results)} pages accessible to YamieBot:\n")
            
            for i, page in enumerate(results, 1):
                # Get page title
                title = "Untitled"
                if "properties" in page:
                    # Try to find title property
                    for prop_name, prop_value in page["properties"].items():
                        if prop_value.get("type") == "title":
                            title_content = prop_value.get("title", [])
                            if title_content:
                                title = title_content[0].get("plain_text", "Untitled")
                                break
                
                # If no title in properties, check for child_page title
                if title == "Untitled" and page.get("parent", {}).get("type") == "page_id":
                    # This is a child page, title might be in different place
                    pass
                
                page_id = page["id"]
                page_url = page.get("url", "")
                
                print(f"  {i}. {title}")
                print(f"     ID: {page_id}")
                print(f"     URL: {page_url}")
                print()
            
            return True
            
        elif response.status_code == 401:
            print(f"\n❌ AUTHENTICATION FAILED (401)")
            print("   Check that your NOTION_API_KEY is correct")
            return False
            
        else:
            print(f"\n❌ API ERROR: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ CONNECTION ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    test_connection()