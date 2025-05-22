import requests
from bs4 import BeautifulSoup, Tag, NavigableString
import re
from typing import List, Dict, Optional
import os
from pyhunter import PyHunter
import time # For potential rate limiting or delays

# Initialize Hunter.io API client using environment variable
HUNTER_API_KEY = os.getenv("HUNTER_IO_API_KEY")
hunter_client = PyHunter(HUNTER_API_KEY) if HUNTER_API_KEY else None

def verify_email_with_hunter(email: str, domain: str) -> Dict[str, str]:
    """
    Verifies an email address using Hunter.io API.
    Returns verification status and details.
    """
    if not hunter_client:
        return {"status": "UNVERIFIED", "details": "Hunter.io API key not configured."}

    # Avoid verifying clearly invalid inferred emails (e.g., 'N/A')
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return {"status": "INVALID", "details": "Invalid email format prior to Hunter.io check."}

    try:
        # Add a small delay to avoid hitting Hunter.io rate limits too quickly
        time.sleep(0.5)
        verification_result = hunter_client.email_verifier(email)

        status_map = {
            'valid': 'VERIFIED',
            'deliverable': 'VERIFIED',
            'invalid': 'INVALID',
            'undeliverable': 'INVALID',
            'unknown': 'UNKNOWN',
            'acceptable': 'VERIFIED'
        }
        status = status_map.get(verification_result.get('result'), 'UNKNOWN')
        details = f"Hunter.io: {verification_result.get('result', 'N/A')} | {verification_result.get('status', 'N/A')}"

        return {"status": status, "details": details}

    except Exception as e:
        print(f"Error verifying email {email} with Hunter.io: {e}")
        # If an API error occurs, treat as UNKNOWN or ERROR_VERIFYING
        return {"status": "ERROR_VERIFYING", "details": f"Hunter.io API error: {str(e)}"}


def _extract_info_from_card(card_element: Tag, domain: str) -> Optional[Dict[str, str]]:
    """
    Attempts to extract name, job title, and infer email from a given HTML card element.
    """
    name = None
    title = None
    inferred_email = 'N/A'

    # Look for name (often in h tags, strong, b)
    name_tags = card_element.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'], text=True)
    if name_tags:
        name_text = name_tags.get_text(strip=True)
        if 1 < len(name_text.split()) < 5 and name_text[0].isupper() and not any(char.isdigit() for char in name_text): # Basic filter for names
            name = name_text

    if not name: # If not found in common name tags, try broader search
        for tag in card_element.find_all(text=True):
            text_content = tag.strip()
            if 1 < len(text_content.split()) < 5 and text_content[0].isupper() and not any(char.isdigit() for char in text_content) and len(text_content) > 5:
                if not re.search(r'^\W+$', text_content): # Avoid purely symbolic text
                    name = text_content
                    break

    # Look for title (often in p, span, div, small)
    if name: # Only look for title if a name was found
        for tag in card_element.find_all(['p', 'span', 'div', 'small'], text=True):
            title_text = tag.get_text(strip=True)
            if title_text != name and 5 < len(title_text) < 100 and " " in title_text and not title_text.isnumeric() and not re.search(r'^\W+$', title_text):
                title = title_text
                break

    if not name: # If name not found, this card is likely not a person
        return None

    # Infer email
    if name and domain:
        first_name_match = re.match(r'(\w+)', name)
        last_name_match = re.search(r'\s(\w+)$', name)

        inferred_email_candidates = []
        if first_name_match and last_name_match:
            first_name = first_name_match.group(1).lower()
            last_name = last_name_match.group(1).lower()
            inferred_email_candidates.extend([
                f"{first_name}.{last_name}@{domain}",
                f"{first_name[0]}{last_name}@{domain}",
                f"{first_name}{last_name}@{domain}",
                f"{first_name}-{last_name}@{domain}",
                f"{last_name}{first_name[0]}@{domain}",
                f"{first_name}@{domain}"
            ])
        elif first_name_match:
            first_name = first_name_match.group(1).lower()
            inferred_email_candidates.append(f"{first_name}@{domain}")

        # Basic validation: take the first candidate that looks like a valid email format
        for candidate in inferred_email_candidates:
            if re.match(r"[^@]+@[^@]+\.[^@]+", candidate):
                inferred_email = candidate
                break

    # Perform Hunter.io verification
    verification_result = verify_email_with_hunter(inferred_email, domain)

    return {
        "name": name,
        "job_title": title if title else "N/A", # Default title if not found
        "company": domain,
        "inferred_email": inferred_email,
        "verified_status": verification_result["status"],
        "verification_details": verification_result["details"]
    }


def scrape_company_team_page(url: str) -> List[Dict[str, str]]:
    """
    Scrapes a company's 'About Us' or 'Team' page for employee leads.
    Uses a generalized approach to find "person cards" and extracts info.
    """
    employees_data = []
    parsed_url = requests.utils.urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]

    if not domain:
        print(f"Could not extract domain from URL: {url}")
        return []

    try:
        response = requests.get(url, timeout=15) # Increased timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Generalized Card-Based Heuristics ---
        # Look for common containers that hold individual team members:
        # div elements with classes like 'team-member', 'person-card', 'member-box', 'col', 'grid-item'
        # li elements within ul with similar class names

        # Start with broad search for divs/list items that might contain a person
        potential_person_containers = soup.find_all(['div', 'li'], class_=re.compile(r'(team|member|person|staff|employee|author|card|profile|bio)'))

        if not potential_person_containers:
            # Fallback: if no specific class, look for common parent-child structures
            # e.g., a div containing multiple h3/h4/p that might be names/titles
            potential_person_containers = soup.find_all('div', class_=re.compile(r'(section|container|wrap)'))
            # Filter these further based on content (e.g., must contain an h tag and a p tag)
            potential_person_containers = [
                container for container in potential_person_containers
                if container.find(['h2', 'h3', 'h4']) and container.find(['p', 'span'])
            ]

        for container in potential_person_containers:
            person_data = _extract_info_from_card(container, domain)
            if person_data and person_data.get("name") and person_data.get("inferred_email") != "N/A":
                employees_data.append(person_data)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during scraping {url}: {e}")
        return []

    # Remove potential duplicates based on inferred_email before returning
    unique_emails = set()
    unique_employees = []
    for emp in employees_data:
        if emp['inferred_email'] not in unique_emails and emp['inferred_email'] != 'N/A':
            unique_emails.add(emp['inferred_email'])
            unique_employees.append(emp)

    return unique_employees

if __name__ == "__main__":
    # For local testing, ensure HUNTER_IO_API_KEY is set in your environment
    # e.g., in Windows Command Prompt: set HUNTER_IO_API_KEY="YOUR_API_KEY"
    # in Linux/macOS Terminal: export HUNTER_IO_API_KEY="YOUR_API_KEY"

    test_urls = [
        "https://www.scrapingbee.com/team/", # Known good
        "https://www.zyte.com/about/team/", # Another structured one
        # "https://aiprecision.agency/about/" # Test with a previously failing one, might still fail but improved
    ]

    for url in test_urls:
        print(f"\n--- Scraping and verifying from: {url} ---")
        scraped_leads = scrape_company_team_page(url)
        if scraped_leads:
            for lead in scraped_leads:
                print(lead)
        else:
            print("No leads scraped from this URL or an error occurred.")