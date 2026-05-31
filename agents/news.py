"""
agents/news.py — News Intelligence Agent
Fetches and categorises recent news about a company.
Primary: NewsAPI    Fallback: Google News RSS
"""

import os
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

CATEGORY_KEYWORDS = {
    "funding": ["raises", "funding", "series", "seed", "million", "billion", "backed", "investment"],
    "product_launch": ["launches", "announces", "introduces", "new feature", "released"],
    "partnership": ["partners", "partnership", "integrates", "collaboration"],
    "hiring": ["hiring", "headcount", "expands team", "new office"],
    "expansion": ["expands", "enters", "new market", "international", "global"],
}

GOOGLE_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


class NewsAgent:
    def get_news(self, company_name: str, domain: str) -> dict:
        """
        Try NewsAPI first. Fall back to Google News RSS if unavailable.
        Never raises — returns dict with news_success: False on total failure.
        """
        try:
            from config import get_news_api_key
            api_key = get_news_api_key()
        except ImportError:
            api_key = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY", "")

        if api_key:
            try:
                return self._fetch_newsapi(company_name, api_key)
            except Exception as e:
                # Fall through to RSS fallback
                pass

        # Fallback
        try:
            return self._fetch_google_rss(company_name)
        except Exception as e:
            return {
                "articles": [],
                "funding_news": [],
                "recent_launches": [],
                "total_articles": 0,
                "news_source": "none",
                "news_success": False,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Primary: NewsAPI
    # ------------------------------------------------------------------

    def _fetch_newsapi(self, company_name: str, api_key: str) -> dict:
        from newsapi import NewsApiClient

        client = NewsApiClient(api_key=api_key)
        from_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        response = client.get_everything(
            q=f'"{company_name}"',
            language="en",
            sort_by="relevancy",
            page_size=10,
            from_param=from_date,
        )

        raw_articles = response.get("articles", [])
        articles = []
        for a in raw_articles:
            title = a.get("title") or ""
            description = a.get("description") or ""
            combined = f"{title} {description}".lower()

            if company_name.lower() not in combined:
                continue  # filter irrelevant

            articles.append({
                "title": title,
                "source": (a.get("source") or {}).get("name", ""),
                "date": a.get("publishedAt", ""),
                "description": description,
                "category": self._categorise(combined),
                "url": a.get("url", ""),
            })

        return self._build_result(articles, source="newsapi")

    # ------------------------------------------------------------------
    # Fallback: Google News RSS
    # ------------------------------------------------------------------

    def _fetch_google_rss(self, company_name: str) -> dict:
        query = quote_plus(f'"{company_name}"')
        url = GOOGLE_RSS_URL.format(query=query)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")[:10]

        articles = []
        for item in items:
            title = item.find("title")
            pub_date = item.find("pubDate")
            link = item.find("link")

            title_text = title.get_text() if title else ""
            combined = title_text.lower()

            articles.append({
                "title": title_text,
                "source": "Google News",
                "date": pub_date.get_text() if pub_date else "",
                "description": "",
                "category": self._categorise(combined),
                "url": link.get_text() if link else "",
            })

        return self._build_result(articles, source="google_rss_fallback")

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _categorise(self, text: str) -> str:
        text_lower = text.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return "other"

    def _build_result(self, articles: list, source: str) -> dict:
        funding_news = [a for a in articles if a["category"] == "funding"]
        recent_launches = [a for a in articles if a["category"] == "product_launch"]

        return {
            "articles": articles,
            "funding_news": funding_news,
            "recent_launches": recent_launches,
            "total_articles": len(articles),
            "news_source": source,
            "news_success": True,
        }
