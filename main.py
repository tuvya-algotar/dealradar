import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import argparse
import asyncio
import concurrent.futures
import os
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

console = Console()

def run_pipeline(domain: str, product_description: str, status_callback=None) -> dict:
    """
    Full DealRadar pipeline. Returns dict with brief_data and pdf_path.
    """
    console.print(Panel(f"[bold blue]🎯 DealRadar[/bold blue] · Researching {domain}", expand=False))
    
    results = {}
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        
        # Stage 1: Parallel data gathering
        task1 = progress.add_task("[cyan]Scraping website...", total=None)
        task2 = progress.add_task("[cyan]Fetching news...", total=None)
        task3 = progress.add_task("[cyan]Analyzing tech stack...", total=None)
        task4 = progress.add_task("[cyan]Reading LinkedIn signals...", total=None)
        
        from agents.scraper import WebScraper
        from agents.news import NewsAgent
        from agents.techstack import TechStackAgent
        from agents.linkedin import LinkedInAgent
        from agents.jobs import JobsAgent
        from agents.synthesizer import Synthesizer
        from memory.store import MemoryStore
        from output.renderer import PDFRenderer
        
        # Run all 5 agents in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_scrape = executor.submit(WebScraper().scrape, domain)
            future_news = executor.submit(NewsAgent().get_news, domain.split('.')[0].title(), domain)
            future_tech = executor.submit(TechStackAgent().get_techstack, domain)
            future_linkedin = executor.submit(LinkedInAgent().get_signals, domain.split('.')[0].title(), domain)
            future_jobs = executor.submit(JobsAgent().get_job_signals, domain)
            
            try:
                scrape_data = future_scrape.result(timeout=30)
                if scrape_data.get("error") or not scrape_data.get("scrape_success", True):
                    progress.update(task1, description="[yellow]⚠ Website scrape partially failed")
                    if status_callback: status_callback("⚠ Website scrape partially failed")
                else:
                    progress.update(task1, description="[green]✓ Website scraped")
                    if status_callback: status_callback("✓ Website scraped")
            except Exception as e:
                scrape_data = {"error": str(e), "scrape_success": False}
                progress.update(task1, description="[yellow]⚠ Website scrape failed")
                if status_callback: status_callback("⚠ Website scrape failed")
            
            try:
                news_data = future_news.result(timeout=30)
                if news_data.get("error") or not news_data.get("news_success", True):
                    progress.update(task2, description="[yellow]⚠ News fetch partially failed")
                    if status_callback: status_callback("⚠ News fetch partially failed")
                else:
                    progress.update(task2, description="[green]✓ News fetched")
                    if status_callback: status_callback("✓ News fetched")
            except Exception as e:
                news_data = {"error": str(e), "news_success": False}
                progress.update(task2, description="[yellow]⚠ News fetch failed")
                if status_callback: status_callback("⚠ News fetch failed")
            
            try:
                tech_data = future_tech.result(timeout=30)
                if tech_data.get("error") or not tech_data.get("tech_success", True):
                    progress.update(task3, description="[yellow]⚠ Tech stack analysis partially failed")
                    if status_callback: status_callback("⚠ Tech stack analysis partially failed")
                else:
                    progress.update(task3, description="[green]✓ Tech stack analyzed")
                    if status_callback: status_callback("✓ Tech stack analyzed")
            except Exception as e:
                tech_data = {"error": str(e), "tech_success": False}
                progress.update(task3, description="[yellow]⚠ Tech stack analysis failed")
                if status_callback: status_callback("⚠ Tech stack analysis failed")
            
            try:
                linkedin_data = future_linkedin.result(timeout=30)
                if linkedin_data.get("error") or not linkedin_data.get("linkedin_success", True):
                    progress.update(task4, description="[yellow]⚠ LinkedIn signals partially failed")
                    if status_callback: status_callback("⚠ LinkedIn signals partially failed")
                else:
                    progress.update(task4, description="[green]✓ LinkedIn signals read")
                    if status_callback: status_callback("✓ LinkedIn signals read")
            except Exception as e:
                linkedin_data = {"error": str(e), "linkedin_success": False}
                progress.update(task4, description="[yellow]⚠ LinkedIn signals failed")
                if status_callback: status_callback("⚠ LinkedIn signals failed")
            
            try:
                jobs_data = future_jobs.result(timeout=15)
            except Exception as e:
                jobs_data = {"jobs": [], "job_count": 0, "hiring_themes": [], "jobs_success": False}
        
        # Stage 2: Check memory for previous research
        memory = MemoryStore()
        is_returning = memory.has_previous_research(domain)
        
        # Stage 3: Synthesize with Claude
        task5 = progress.add_task("[magenta]Synthesizing intelligence with Claude...", total=None)
        
        synthesizer = Synthesizer()
        try:
            brief_data = synthesizer.synthesize(
                domain=domain,
                product_description=product_description,
                scrape_data=scrape_data,
                news_data=news_data,
                tech_data=tech_data,
                linkedin_data=linkedin_data
            )
        except Exception as e:
            brief_data = {"error": f"Synthesis failed: {e}", "company_name": domain, "deal_readiness_score": {"score": 0, "label": "Error"}}
        progress.update(task5, description="[green]✓ Intelligence synthesized")
        if status_callback: status_callback("✓ Intelligence synthesized")
        
        # Stage 4: Save to memory + generate diff
        task6 = progress.add_task("[yellow]Saving to memory...", total=None)
        research_id = memory.save_research(domain, brief_data, scrape_data, news_data, tech_data, linkedin_data, jobs_data)
        
        diff_data = None
        if is_returning:
            diffs = memory.get_diff_history(domain)
            if diffs:
                diff_data = diffs[0]  # Most recent diff
        progress.update(task6, description="[green]✓ Memory updated")
        if status_callback: status_callback("✓ Memory updated")
        
        # Stage 5: Generate PDF
        task7 = progress.add_task("[blue]Generating PDF report...", total=None)
        
        from output.renderer import PDFRenderer, WEASYPRINT_AVAILABLE
        import re
        safe_domain = re.sub(r'[^a-zA-Z0-9]', '_', domain)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        os.makedirs("reports", exist_ok=True)
        if WEASYPRINT_AVAILABLE:
            pdf_path = f"reports/{safe_domain}_{timestamp}.pdf"
        else:
            pdf_path = f"reports/{safe_domain}_{timestamp}.html"
        
        renderer = PDFRenderer()
        try:
            renderer.render(brief_data, domain, pdf_path)
            progress.update(task7, description=f"[green]✓ Report saved: {pdf_path}")
            if status_callback: status_callback("✓ Report saved")
        except Exception as e:
            pdf_path = None
            progress.update(task7, description=f"[yellow]⚠ Report generation failed: {e}")
            if status_callback: status_callback("⚠ Report generation failed")
    
    console.print(Panel(
        f"[bold green]✓ Brief complete![/bold green]\n"
        f"Company: {brief_data.get('company_name')}\n"
        f"Deal Score: {brief_data.get('deal_readiness_score', {}).get('score')}/10 "
        f"({brief_data.get('deal_readiness_score', {}).get('label')})\n"
        f"PDF: {pdf_path}",
        expand=False
    ))
    
    return {
        "brief_data": brief_data,
        "pdf_path": pdf_path,
        "diff_data": diff_data,
        "is_returning_company": is_returning,
        "research_id": research_id,
        "jobs_data": jobs_data
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DealRadar Pre-Call Brief Generator")
    parser.add_argument("--domain", required=True, help="Domain to research")
    parser.add_argument("--product", required=True, help="Your product description")
    args = parser.parse_args()
    
    run_pipeline(args.domain, args.product)
