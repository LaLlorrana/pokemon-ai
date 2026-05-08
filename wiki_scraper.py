# ============================================================
#  wiki_scraper.py — Pokémon Unbound Wiki downloader
#  Run this ONCE to download the full wiki to your project folder.
#
#  Usage:
#    pip install requests beautifulsoup4
#    python wiki_scraper.py
# ============================================================

import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# --- Config ---
BASE_URL   = "https://unboundwiki.com"
START_URLS = [
    "https://unboundwiki.com/",
    "https://unboundwiki.com/walkthrough/",
    "https://unboundwiki.com/pokemon/",
    "https://unboundwiki.com/items/",
    "https://unboundwiki.com/locations/",
    "https://unboundwiki.com/missions/",
    "https://unboundwiki.com/gyms/",
    "https://unboundwiki.com/mega-stones/",
    "https://unboundwiki.com/tms-hms/",
    "https://unboundwiki.com/raid-dens/",
    "https://unboundwiki.com/extras/",
    "https://unboundwiki.com/misc-info/",
    "https://unboundwiki.com/z-crystals/",
    "https://unboundwiki.com/categories",
]
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "wiki_data")
INDEX_FILE = os.path.join(OUTPUT_DIR, "_index.json")
DELAY      = 0.4    # seconds between requests
MAX_PAGES  = 3000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Skip these URL patterns
SKIP_PATTERNS = [
    "/wp-", "/wp-content/", "/wp-admin/", "/feed/", "/tag/",
    "/author/", "/page/", "?", "#", "mailto:", "javascript:",
    "/cdn-cgi/", "/comment-", ".jpg", ".png", ".gif", ".pdf",
    ".zip", ".css", ".js",
]


def slugify(url: str) -> str:
    """Turn a URL into a safe filename."""
    path = urlparse(url).path.strip("/").replace("/", "_") or "index"
    path = re.sub(r'[\\/*?:"<>|]', '_', path)
    return (path[:100] + ".txt")


def should_skip(url: str) -> bool:
    if not url.startswith(BASE_URL):
        return True
    return any(p in url for p in SKIP_PATTERNS)


def extract_text(soup: BeautifulSoup, url: str) -> tuple[str, str]:
    """Extract page title and clean body text."""
    # Title
    title = ""
    for sel in ["h1.entry-title", "h1.page-title", "h1", "title"]:
        tag = soup.select_one(sel)
        if tag:
            title = tag.get_text(strip=True)
            break

    # Content — try common WordPress/custom content divs
    content = None
    for sel in [".entry-content", ".page-content", "article", "main", "#content", ".content"]:
        content = soup.select_one(sel)
        if content:
            break

    if not content:
        content = soup.find("body")
    if not content:
        return title, ""

    # Remove noise
    for tag in content.find_all(["script", "style", "nav", "footer",
                                  "header", ".sidebar", ".widget",
                                  ".advertisement", "noscript", "iframe"]):
        tag.decompose()

    text = content.get_text(separator="\n", strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return title or url, text.strip()


def get_links(soup: BeautifulSoup) -> set:
    """Get all internal links from a page."""
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Make absolute
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.startswith("http"):
            continue
        href = href.split("#")[0].split("?")[0]  # strip anchors & params
        if not should_skip(href):
            links.add(href.rstrip("/") + "/" if not "." in href.split("/")[-1] else href)
    return links


def scrape():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    visited = set()
    queue   = list(START_URLS)
    index   = {}
    count   = 0

    print(f"Scraping unboundwiki.com → {OUTPUT_DIR}\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    while queue and count < MAX_PAGES:
        url = queue.pop(0)
        # Normalise URL
        url = url.rstrip("/") + "/"
        if url in visited or should_skip(url):
            continue
        visited.add(url)

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  SKIP [{resp.status_code}] {url}")
                continue
        except Exception as e:
            print(f"  ERROR: {url} — {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title, text = extract_text(soup, url)

        if len(text) < 100:
            # Skip pages with barely any content
            for link in get_links(soup):
                if link not in visited:
                    queue.append(link)
            continue

        filename = slugify(url)
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\nSource: {url}\n\n{text}")

        index[filename] = title
        count += 1
        print(f"  [{count}] {title}  ({url})")

        for link in get_links(soup):
            if link not in visited:
                queue.append(link)

        time.sleep(DELAY)

    # Save index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"\n✅ Done! Scraped {count} pages.")
    print(f"   Restart PokeBot to load the wiki knowledge base.")


if __name__ == "__main__":
    scrape()
