import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import os
from pyhunter import PyHunter # Corrected: Import PyHunter API client

# Initialize Hunter.io API client using environment variable
# This will be None if HUNTER_IO_API_KEY is not set (e.g., local dev without it)
HUNTER_API_KEY = os.getenv("HUNTER_IO_API_KEY")
hunter_client = PyHunter(HUNTER_API_KEY) if HUNTER_API_KEY else None

def verify_email_with_hunter(email: str, domain: str) -> Dict[str, str]:
    """
    Verifies an email address using Hunter.io API.
    Returns verification status and details.
    """
    if not hunter_client:
        # Fallback if API key is not set (e.g., during local development)
        return {"status": "UNVERIFIED", "details": "Hunter.io API key not configured."}

    try:
        # Hunter.io's email verification endpoint
        # Returns a dictionary with 'result', 'score', 'regexp', 'gibberish', etc.
        # 'result' can be 'valid', 'invalid', 'unknown', 'deliverable', 'undeliverable'
        verification_result = hunter_client.email_verifier(email)

        # Map Hunter.io's result to your simplified status
        # 'valid' and 'deliverable' are generally good. 'invalid' and 'undeliverable' are bad.
        # 'unknown' means Hunter couldn't determine.
        status_map = {
            'valid': 'VERIFIED',
            'deliverable': 'VERIFIED',
            'invalid': 'INVALID',
            'undeliverable': 'INVALID',
            'unknown': 'UNKNOWN', # Could not verify, treat with caution
            'acceptable': 'VERIFIED' # Hunter's 'acceptable' status
        }
        status = status_map.get(verification_result.get('result'), 'UNKNOWN')
        details = verification_result.get('result', 'N/A') + " | " + \
                  verification_result.get('status', 'N/A') # More detailed status

        return {"status": status, "details": details}

    except Exception as e:
        # Log error if Hunter.io API call fails for any reason
        print(f"Error verifying email {email} with Hunter.io: {e}")
        return {"status": "ERROR_VERIFYING", "details": str(e)}


def scrape_company_team_page(url: str) -> List[Dict[str, str]]:
    """
    Scrapes a company's 'About Us' or 'Team' page for employee names and job titles.
    Infers email addresses and verifies them using Hunter.io.
    """
    employees_data = []
    # Extract domain from URL robustly
    parsed_url = requests.utils.urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]

    if not domain:
        print(f"Could not extract domain from URL: {url}")
        return []

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        potential_name_tags = soup.find_all(['h2', 'h3', 'h4'])

        for name_tag in potential_name_tags:
            name_text = name_tag.get_text(strip=True)

            if not name_text or len(name_text.split()) < 2 or len(name_text) > 50:
                continue
            if not name_text[0].isupper():
                continue

            title = 'N/A'
            next_sibling = name_tag.next_sibling
            if next_sibling:
                if hasattr(next_sibling, 'get_text'):
                    potential_title_text = next_sibling.get_text(strip=True)
                    if 5 < len(potential_title_text) < 100 and " " in potential_title_text and not potential_title_text.isnumeric():
                        title = potential_title_text

            if title == 'N/A':
                parent_container = name_tag.find_parents(lambda tag: tag.name == 'div' and ('team' in tag.get('class', []) or 'person' in tag.get('class', []) or 'elementor-widget-wrap' in tag.get('class', [])), limit=3)
                if parent_container:
                    for p_tag in parent_container[0].find_all(['p', 'div', 'span']): # [0] to get the first parent if multiple
                        p_text = p_tag.get_text(strip=True)
                        if p_text != name_text and 5 < len(p_text) < 100 and " " in p_text and not p_text.isnumeric():
                            title = p_text
                            break

            if name_text and title:
                inferred_email = 'N/A'
                first_name_match = re.match(r'(\w+)', name_text)
                last_name_match = re.search(r'\s(\w+)$', name_text)

                if first_name_match and last_name_match:
                    first_name = first_name_match.group(1).lower()
                    last_name = last_name_match.group(1).lower()
                    # Prioritize common pattern: firstname.lastname
                    inferred_email_candidates = [
                        f"{first_name}.{last_name}@{domain}",
                        f"{first_name[0]}{last_name}@{domain}",
                        f"{first_name}@{domain}" # Less common, but a fallback
                    ]
                    for candidate in inferred_email_candidates:
                        # Basic validation: check if it looks like an email
                        if re.match(r"[^@]+@[^@]+\.[^@]+", candidate):
                            inferred_email = candidate
                            break # Use the first valid looking candidate

                elif first_name_match:
                    first_name = first_name_match.group(1).lower()
                    inferred_email = f"{first_name}@{domain}"

                verification_result = verify_email_with_hunter(inferred_email, domain)

                employees_data.append({
                    "name": name_text,
                    "job_title": title,
                    "company": domain,
                    "inferred_email": inferred_email,
                    "verified_status": verification_result["status"],
                    "verification_details": verification_result["details"]
                })

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during scraping {url}: {e}")
        return []

    return employees_data

if __name__ == "__main__":
    # For local testing with Hunter.io, you MUST set HUNTER_IO_API_KEY
    # e.g., export HUNTER_IO_API_KEY="YOUR_API_KEY" in terminal
    # Or add it to your environment variables
    test_url = "https://www.scrapingbee.com/team/"
    print(f"Scraping and verifying from: {test_url}")
    scraped_leads = scrape_company_team_page(test_url)
    for lead in scraped_leads:
        print(lead)