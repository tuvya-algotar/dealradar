"""
test_agents.py — Run all 4 agents against notion.so and print results via rich.
Usage: python test_agents.py
"""

import json
import sys
import traceback

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

# Add project root so agents/ is importable even when run directly
sys.path.insert(0, ".")

from agents.scraper import WebScraper
from agents.news import NewsAgent
from agents.techstack import TechStackAgent
from agents.linkedin import LinkedInAgent

DOMAIN = "notion.so"
COMPANY = "Notion"

console = Console()


def run_agent(label: str, fn):
    """Run a single agent function, catch all exceptions, pretty-print the result."""
    console.print(Rule(f"[bold cyan]{label}[/bold cyan]"))
    try:
        result = fn()
        console.print(
            Panel(
                json.dumps(result, indent=2, default=str),
                title=f"[green]{label} — SUCCESS[/green]",
                expand=False,
            )
        )
        return result
    except Exception:
        console.print(f"[bold red]{label} raised an unexpected exception:[/bold red]")
        console.print(traceback.format_exc())
        return None


def main():
    console.print(Rule("[bold magenta]DealRadar Agent Test Suite[/bold magenta]"))
    console.print(f"[dim]Target: {COMPANY} / {DOMAIN}[/dim]\n")

    # 1. WebScraper
    run_agent(
        "WebScraper",
        lambda: WebScraper().scrape(DOMAIN),
    )

    # 2. NewsAgent
    run_agent(
        "NewsAgent",
        lambda: NewsAgent().get_news(COMPANY, DOMAIN),
    )

    # 3. TechStackAgent
    run_agent(
        "TechStackAgent",
        lambda: TechStackAgent().get_techstack(DOMAIN),
    )

    # 4. LinkedInAgent
    run_agent(
        "LinkedInAgent",
        lambda: LinkedInAgent().get_signals(COMPANY, DOMAIN),
    )

    console.print(Rule("[bold magenta]All agents completed[/bold magenta]"))


if __name__ == "__main__":
    main()
