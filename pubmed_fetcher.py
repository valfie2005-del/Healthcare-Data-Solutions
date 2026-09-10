"""
PubMed Article Fetcher
-----------------------
A simple beginner-friendly Python program that searches PubMed for articles
matching a keyword and displays details for up to 50 articles in the terminal.

It uses NCBI's E-utilities API:
    1. esearch - to find PubMed IDs (PMIDs) matching a search keyword
    2. efetch  - to fetch full article details for those PMIDs

Libraries used:
    - requests               (to make HTTP calls to the API)
    - xml.etree.ElementTree  (to parse the XML response from efetch)

Design note: every function below takes arguments and returns data
(no input()/print() inside them). This keeps the core logic reusable —
later, a Django view can import and call these same functions directly,
passing the returned dicts straight into a template or JSON response.
"""

import requests
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
import os

load_dotenv()



# Base URL for all NCBI E-utilities calls
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

API_KEY = os.getenv("PUMMED_API_KEY")

# How many articles we want to fetch at a time
MAX_RESULTS = 100


def search_pubmed(keyword, max_results=MAX_RESULTS):
    """
    Use the 'esearch' endpoint to search PubMed for a keyword
    and return a list of matching PubMed IDs (PMIDs).
    """
    url = f"{BASE_URL}/esearch.fcgi"

    params = {
        "db": "pubmed",         # We are searching the PubMed database
        "term": keyword,        # The search keyword typed by the user
        "retmax": max_results,  # Limit results (default 50)
        "retmode": "xml",       # Ask for the response in XML format
        "api_key": API_KEY      # Your NCBI API key
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raises an error if the request failed
    except requests.exceptions.RequestException as e:
        print(f"Error while searching PubMed: {e}")
        return []

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        print(f"Error parsing search results: {e}")
        return []

    pmid_list = [id_elem.text for id_elem in root.findall(".//Id")]
    return pmid_list


def fetch_articles_xml(pmid_list):
    """
    Use the 'efetch' endpoint to retrieve full details for the given
    PubMed IDs. Returns the parsed XML tree (or None on failure).
    """
    if not pmid_list:
        return None

    url = f"{BASE_URL}/efetch.fcgi"

    params = {
        "db": "pubmed",
        "id": ",".join(pmid_list),  # Combine all PMIDs into one comma-separated string
        "retmode": "xml",
        "api_key": API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error while fetching article details: {e}")
        return None

    try:
        return ET.fromstring(response.text)
    except ET.ParseError as e:
        print(f"Error parsing article details: {e}")
        return None


def parse_article(article_elem):
    """
    Extract useful fields from a single <PubmedArticle> XML element.
    Uses safe lookups so missing fields don't crash the program.
    """

    # --- PubMed ID ---
    pmid_elem = article_elem.find(".//PMID")
    pmid = pmid_elem.text if pmid_elem is not None else "N/A"

    # --- Title ---
    title_elem = article_elem.find(".//ArticleTitle")
    title = title_elem.text if title_elem is not None and title_elem.text else "No title available"

    # --- Journal name ---
    journal_elem = article_elem.find(".//Journal/Title")
    journal = journal_elem.text if journal_elem is not None and journal_elem.text else "Unknown journal"

    # --- Publication date (year/month/day may or may not all be present) ---
    year_elem = article_elem.find(".//JournalIssue/PubDate/Year")
    month_elem = article_elem.find(".//JournalIssue/PubDate/Month")
    day_elem = article_elem.find(".//JournalIssue/PubDate/Day")

    year = year_elem.text if year_elem is not None else ""
    month = month_elem.text if month_elem is not None else ""
    day = day_elem.text if day_elem is not None else ""

    pub_date = " ".join(part for part in [month, day, year] if part).strip()
    if not pub_date:
        pub_date = "Date not available"

    # --- Authors ---
    authors_list = []
    for author_elem in article_elem.findall(".//AuthorList/Author"):
        last_name = author_elem.find("LastName")
        fore_name = author_elem.find("ForeName")

        if last_name is not None and fore_name is not None:
            authors_list.append(f"{fore_name.text} {last_name.text}")
        elif last_name is not None:
            authors_list.append(last_name.text)

    authors = ", ".join(authors_list) if authors_list else "No authors listed"

    # --- Abstract (can have multiple <AbstractText> sections) ---
    abstract_parts = []
    for abstract_elem in article_elem.findall(".//Abstract/AbstractText"):
        if abstract_elem.text:
            abstract_parts.append(abstract_elem.text)

    abstract = " ".join(abstract_parts) if abstract_parts else "No abstract available"

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "pub_date": pub_date,
        "abstract": abstract
    }


def fetch_articles(pmid_list):
    """
    High-level function: takes a list of PMIDs, returns a list of
    clean article dictionaries. This is the function a Django view
    would call - it hides all the XML handling behind a simple interface.
    """
    root = fetch_articles_xml(pmid_list)
    if root is None:
        return []
    return [parse_article(article_elem) for article_elem in root.findall(".//PubmedArticle")]


def display_articles(articles):
    """
    Print article details to the terminal in a clear, readable format.
    (This is the one function that's terminal-only / not reused by Django -
    a Django view would render a template instead of calling this.)
    """
    if not articles:
        print("No articles found.")
        return

    print(f"\nFound {len(articles)} article(s):\n")
    print("=" * 80)

    for i, article in enumerate(articles, start=1):
        print(f"Article #{i}")
        print(f"PubMed ID   : {article['pmid']}")
        print(f"Title       : {article['title']}")
        print(f"Authors     : {article['authors']}")
        print(f"Journal     : {article['journal']}")
        print(f"Pub. Date   : {article['pub_date']}")
        print(f"Abstract    : {article['abstract']}")
        print("=" * 80)


def main():
    """
    Main program flow (terminal only):
    1. Ask the user for a search keyword
    2. Search PubMed for matching PMIDs (up to 50)
    3. Fetch full details for those PMIDs
    4. Display the results in the terminal
    """
    print("PubMed Article Fetcher")
    print("-----------------------")
    keyword = input("Enter a search keyword (e.g. 'machine learning', 'breast cancer'): ").strip()

    if not keyword:
        print("You did not enter a keyword. Exiting.")
        return

    print(f"\nSearching PubMed for '{keyword}'...")
    pmid_list = search_pubmed(keyword)

    if not pmid_list:
        print("No results found or an error occurred during search.")
        return

    print(f"Found {len(pmid_list)} PubMed ID(s). Fetching article details...")
    articles = fetch_articles(pmid_list)

    display_articles(articles)


# Standard Python entry point check - only runs main() when this
# file is executed directly (e.g. `python pubmed_fetcher.py`).
# When Django imports this file later, this block is skipped entirely.
if __name__ == "__main__":
    main()