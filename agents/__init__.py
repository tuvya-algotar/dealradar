"""
agents/__init__.py — Export all agent classes for clean imports.
"""

from agents.scraper import WebScraper
from agents.news import NewsAgent
from agents.techstack import TechStackAgent
from agents.linkedin import LinkedInAgent
from agents.synthesizer import Synthesizer

__all__ = ["WebScraper", "NewsAgent", "TechStackAgent", "LinkedInAgent", "Synthesizer"]
