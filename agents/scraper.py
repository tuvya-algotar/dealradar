"""
agents/scraper.py — Website Intelligence Agent
Scrapes company website for key signals: title, description, about, blog, funding mentions.
"""

import re
import requests
from bs4 import BeautifulSoup


HEADERS_PRIMARY = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HEADERS_FALLBACK = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.8",
}

FUNDING_KEYWORDS = ["fund", "invest", "raise", "series", "seed", "backed"]


class WebScraper:
    def scrape(self, domain: str) -> dict:
        """
        Primary scrape: hits homepage, /about, /blog.
        Falls back to a single homepage fetch with alternate UA on any failure.
        """
        base = domain.rstrip("/")
        if not base.startswith("http"):
            base = f"https://{base}"

        urls = {
            "home": base,
            "about": f"{base}/about",
            "blog": f"{base}/blog",
        }

        try:
            return self._scrape_all(domain, urls, HEADERS_PRIMARY)
        except Exception as primary_err:
            # Fallback: single homepage fetch with alternate UA
            try:
                resp = requests.get(urls["home"], headers=HEADERS_FALLBACK, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                return self._build_result(
                    domain=domain,
                    soup_home=soup,
                    soup_about=None,
                    soup_blog=None,
                    success=True,
                )
            except Exception as fallback_err:
                return {
                    "domain": domain,
                    "company_name": "",
                    "meta_description": "",
                    "homepage_text": "",
                    "about_text": "",
                    "recent_blog_titles": [],
                    "funding_mentions": "",
                    "scrape_success": False,
                    "error": "Could not access domain",
                }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(self, url: str, headers: dict) -> BeautifulSoup | None:
        """Fetch URL and return BeautifulSoup, or None on failure."""
        import time
        for n in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except requests.exceptions.ConnectionError:
                print(f"Connection refused or DNS failure")
                print(f"Retrying {url} (attempt {n}/2)...")
                if n == 1:
                    time.sleep(1)
            except Exception:
                print(f"Unexpected error")
                print(f"Retrying {url} (attempt {n}/2)...")
                if n == 1:
                    time.sleep(1)
        return None

    def _scrape_all(self, domain: str, urls: dict, headers: dict) -> dict:
        """Hit all three URLs and aggregate results."""
        soup_home = self._fetch(urls["home"], headers)
        if soup_home is None:
            raise ConnectionError(f"Failed to fetch {urls['home']}")

        soup_about = self._fetch(urls["about"], headers)
        soup_blog = self._fetch(urls["blog"], headers)

        return self._build_result(domain, soup_home, soup_about, soup_blog, success=True)

    def _build_result(
        self,
        domain: str,
        soup_home: BeautifulSoup,
        soup_about: BeautifulSoup | None,
        soup_blog: BeautifulSoup | None,
        success: bool,
    ) -> dict:
        # ---- Homepage ----
        company_name = self._get_title(soup_home)
        meta_desc = self._get_meta_description(soup_home)
        full_homepage_text = self._get_body_text(soup_home, max_chars=3000)
        funding_mentions = self._extract_funding_mentions(full_homepage_text)
        homepage_text = full_homepage_text[:2000]

        # ---- About page ----
        about_text = ""
        if soup_about:
            about_text = self._get_body_text(soup_about, max_chars=1000)

        # ---- Blog page ----
        recent_blog_titles = []
        if soup_blog:
            recent_blog_titles = self._extract_blog_titles(soup_blog)

        return {
            "domain": domain,
            "company_name": company_name,
            "meta_description": meta_desc,
            "homepage_text": homepage_text,
            "about_text": about_text,
            "recent_blog_titles": recent_blog_titles,
            "funding_mentions": funding_mentions,
            "scrape_success": success,
        }

    def _get_title(self, soup: BeautifulSoup) -> str:
        tag = soup.find("title")
        return self._clean(tag.get_text()) if tag else ""

    def _get_meta_description(self, soup: BeautifulSoup) -> str:
        tag = soup.find("meta", attrs={"name": "description"})
        if tag and tag.get("content"):
            return self._clean(tag["content"])
        tag = soup.find("meta", attrs={"property": "og:description"})
        if tag and tag.get("content"):
            return self._clean(tag["content"])
        return ""

    def _get_body_text(self, soup: BeautifulSoup, max_chars: int) -> str:
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(separator=" ") for p in paragraphs[:40])
        text = self._clean(text)
        return text[:max_chars]

    def _extract_blog_titles(self, soup: BeautifulSoup) -> list:
        titles = []
        for tag in ["h1", "h2", "h3"]:
            for el in soup.find_all(tag):
                t = self._clean(el.get_text())
                if t and len(t) > 10:
                    titles.append(t)
                if len(titles) >= 5:
                    return titles
        # Fallback: article titles
        for a in soup.find_all("a", href=True):
            t = self._clean(a.get_text())
            if t and len(t) > 20:
                titles.append(t)
            if len(titles) >= 5:
                return titles
        return titles[:5]

    def _extract_funding_mentions(self, text: str) -> str:
        sentences = re.split(r'[.!?]', text)
        matches = [
            s.strip()
            for s in sentences
            if any(kw in s.lower() for kw in FUNDING_KEYWORDS)
        ]
        return " | ".join(matches[:5])

    @staticmethod
    def _clean(text: str) -> str:
        """Remove HTML artifacts, collapse whitespace, strip special chars."""
        if not text:
            return ""
        # Remove leftover HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove non-printable chars
        text = re.sub(r"[^\x20-\x7E]", "", text)
        return text.strip()
