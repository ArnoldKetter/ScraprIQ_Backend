import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional

def scrape_company_team_page(url: str) -> List[Dict[str, str]]:
    """
    Scrapes a company's 'About Us' or 'Team' page for employee names and job titles.
    Infers email addresses based on common patterns.
    """
    employees_data = []
    domain = url.replace('https://', '').split('/')[0]

    try:
        response = requests.get(url, timeout=10) # Added timeout for robustness
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Heuristic Scraping Logic ---
        # This is a generalized approach. For an MVP, it will work for many, but not all sites.
        # Names often appear in <h2>, <h3>, <h4> tags. Titles in adjacent <p>, <div>, <span>.
        # Look for common text patterns within a broader container (e.g., Elementor sections)

        # Try finding potential name elements first (h2, h3, h4 commonly used for names)
        potential_name_tags = soup.find_all(['h2', 'h3', 'h4'])

        for name_tag in potential_name_tags:
            name_text = name_tag.get_text(strip=True)

            # Heuristic: Filter out common non-name headings, or very short/long texts
            if not name_text or len(name_text.split()) < 2 or len(name_text) > 50:
                continue # Skip if likely not a name (e.g., "Our Services", very long text)
            if not name_text[0].isupper():
                continue # Skip if doesn't start with capital letter (e.g., css class in text)

            # Try to find a title immediately after the name tag or in its parent/sibling container
            title = 'N/A'
            # Check next sibling first for common patterns (div, p, span)
            next_sibling = name_tag.next_sibling
            if next_sibling:
                if hasattr(next_sibling, 'get_text'): # Check if it's a tag
                    potential_title_text = next_sibling.get_text(strip=True)
                    if 5 < len(potential_title_text) < 100 and " " in potential_title_text and not potential_title_text.isnumeric():
                        title = potential_title_text

            # If not found in immediate sibling, look within common parent
            if title == 'N/A':
                parent_container = name_tag.find_parents(lambda tag: tag.name == 'div' and ('team' in tag.get('class', []) or 'person' in tag.get('class', []) or 'elementor-widget-wrap' in tag.get('class', [])), limit=3)
                if parent_container:
                    # Look for more general text elements within this container that could be titles
                    for p_tag in parent_container.find_all(['p', 'div', 'span']):
                        p_text = p_tag.get_text(strip=True)
                        if p_text != name_text and 5 < len(p_text) < 100 and " " in p_text and not p_text.isnumeric():
                            title = p_text
                            break # Found a plausible title


            if name_text and title: # If both name and a plausible title found
                inferred_email = 'N/A'
                # Basic permutations: firstname.lastname@domain.com, firstinitiallastname@domain.com
                # Further refinement of email generation is a future step for ScraprIQ
                first_name_match = re.match(r'(\w+)', name_text)
                last_name_match = re.search(r'\s(\w+)$', name_text)

                if first_name_match and last_name_match:
                    first_name = first_name_match.group(1).lower()
                    last_name = last_name_match.group(1).lower()
                    inferred_email = f"{first_name}.{last_name}@{domain}"
                elif first_name_match:
                    first_name = first_name_match.group(1).lower()
                    inferred_email = f"{first_name}@{domain}"
                # Add other patterns like firstinitial_lastname, firstname_lastinitial, etc.

                employees_data.append({
                    "name": name_text,
                    "job_title": title,
                    "company": domain, # Default to domain for MVP
                    "inferred_email": inferred_email,
                    "verified_status": "UNVERIFIED",
                    "verification_details": None
                })

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during scraping {url}: {e}")
        return []

    return employees_data

# Example usage (for testing this module directly if needed)
if __name__ == "__main__":
    test_url = "https://aiprecision.agency/about/"
    scraped_leads = scrape_company_team_page(test_url)
    for lead in scraped_leads:
        print(lead)