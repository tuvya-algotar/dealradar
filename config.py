"""
config.py — Centralized Configuration Management
Loads, retrieves, and validates environment variables for DealRadar agents.
Provides backwards compatibility for legacy key names and clean error messages.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

def get_anthropic_api_key() -> str:
    """
    Retrieves ANTHROPIC_API_KEY.
    Raises EnvironmentError if the key is missing since LLM synthesis is critical.
    """
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Please create a .env file and specify your Anthropic API key.\n"
            "Example: ANTHROPIC_API_KEY=your_key_here"
        )
    return key

def get_news_api_key() -> str:
    """
    Retrieves News API key.
    Prioritizes NEWS_API_KEY, falling back to legacy NEWSAPI_KEY.
    Returns empty string if missing (NewsAgent handles fallback to Google News RSS gracefully).
    """
    return (os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY") or "").strip()

def get_builtwith_api_key() -> str:
    """
    Retrieves BuiltWith API key.
    Returns empty string if missing (TechStackAgent handles fallback to HTML parsing gracefully).
    """
    return os.getenv("BUILTWITH_API_KEY", "").strip()

def get_linkdapi_api_key() -> str:
    """
    Retrieves LinkdAPI key.
    Prioritizes LINKDAPI_API_KEY, falling back to legacy LINKDAPI_KEY.
    Returns empty string if missing (LinkedInAgent handles empty state gracefully).
    """
    return (os.getenv("LINKDAPI_API_KEY") or os.getenv("LINKDAPI_KEY") or "").strip()
