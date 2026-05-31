"""
agents/synthesizer.py — Claude LLM Synthesis Agent

Takes raw data from all 4 agents and produces a structured, high-quality
sales intelligence brief via the Anthropic Claude API.

Environment variables:
  ANTHROPIC_API_KEY  — required
  LLM_MODEL          — optional, defaults to claude-opus-4-5
  LLM_BASE_URL       — optional, for TokenRouter swap on event day
"""

import json
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Module-level prompt constants — edit here without touching logic
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an elite B2B sales intelligence analyst with 15 years of experience \
at top sales consultancies. Your job is to analyze raw company intelligence \
data and produce a structured Pre-Call Brief that a senior Account Executive \
would use before a high-stakes cold call.

Your analysis must be:
- SPECIFIC: Reference actual facts from the data, never generic statements
- ACTIONABLE: Every insight must suggest a concrete sales action
- HONEST: If data is sparse, say so — do not fabricate
- CONCISE: Sales reps read this in 60 seconds before a call

You will return a JSON object and NOTHING ELSE. No preamble, no explanation, \
no markdown fences (do not use ```json). Pure JSON only. Ensure ALL keys are present.\
"""

USER_PROMPT_TEMPLATE = """\
Here is the raw intelligence data for the company:

{context}

The sales rep's product: {product_description}

---

## CRITICAL INSTRUCTION — ZERO HALLUCINATION MODE

You are NOT allowed to invent, assume, or estimate ANY fact.

Every claim you generate MUST be directly traceable to the provided data.

Before generating output, follow this internal rule:

1. Extract only verifiable facts from the data
2. Discard anything uncertain or incomplete
3. Build insights ONLY from those verified facts

If you cannot find enough data:
→ Say "Insufficient data to assess"
→ Do NOT compensate with guesses

---

## EVIDENCE REQUIREMENT (STRICT)

For EVERY key_signal:

* The "signal" MUST map to a specific line or fact in the data
* You MUST explicitly reference the origin:
  (e.g. "From news: [short title]" or "From website text")

If you cannot point to a source:
→ DO NOT include that signal

---

## NUMBERS RULE (VERY IMPORTANT)

* NEVER generate numbers unless they appear EXACTLY in the data
* NEVER estimate growth, funding, hiring, or metrics
* NEVER say "likely", "probably", or "suggests" with numbers

Bad:
❌ "4x growth likely causing issues"

Good:
✅ "News mentions '4x growth in Q4' → may indicate scaling pressure"

---

## INFERENCE RULE (CONTROLLED)

You are allowed to make inferences ONLY IF:

* They are clearly marked as inference
* Confidence is set to "low" or "medium"
* The reasoning explicitly connects to a real fact

---

## LINKEDIN DATA RULE

If linkedin_data shows:

* employee_count = "unknown"
* AND no recent_job_titles

Then:

* DO NOT generate any LinkedIn-based signals
* Add: "LinkedIn data unavailable" to data_quality.missing_data_warnings

---

## OUTPUT REQUIREMENTS

Return a JSON object with EXACTLY this structure:

{{
  "company_name": "string — official company name",
  "company_snapshot": "string — 2-3 sentence description of what this company does, who their customers are, and their current market position. Be specific.",

  "key_signals": [
    {{
      "signal": "string — specific observation (e.g. 'Hired 12 ops-focused engineers in last 60 days')",
      "implication": "string — what this means for the sales rep (e.g. 'Scaling operations fast — pain points in workflow likely')",
      "source": "string — where this came from: 'linkedin', 'news', 'website', 'techstack'",
      "confidence": "high|medium|low",
      "confidence_reason": "string — brief reason for this confidence level (e.g. 'Found in 3 independent sources' or 'Inferred from job titles only')"
    }}
  ],

  "talking_points": [
    {{
      "point": "string — a specific, personalized talking point the rep can say verbatim or near-verbatim on the call",
      "why_it_works": "string — the psychological reason this lands (e.g. 'Acknowledges their recent growth challenge directly')",
      "confidence": "high|medium|low",
      "confidence_reason": "string — why you are or aren't confident in this point"
    }}
  ],

  "email_subject_lines": [
    {{
      "subject": "string — personalized subject line under 50 chars",
      "approach": "string — the angle: 'curiosity' | 'pain' | 'compliment' | 'relevance'"
    }}
  ],

  "best_persona_to_target": {{
    "title": "string — exact job title to target (e.g. 'VP of Revenue Operations')",
    "why": "string — reason this person feels the pain most"
  }},

  "competitor_landscape": [
    {{
      "competitor": "string — name of a likely competitor this prospect already uses or evaluates",
      "evidence": "string — what in the data suggests this (e.g. 'HubSpot detected in tech stack')",
      "our_edge": "string — one specific reason your product beats them for this prospect"
    }}
  ],

  "risk_factors": [
    "string — reason this deal might not close (e.g. 'Already uses Salesforce which has overlapping features')"
  ],

  "objection_handler": [
    {{
      "objection": "string — a specific objection this prospect is likely to raise on the call (e.g. 'We already have an internal tool for this')",
      "rebuttal": "string — a concise, confident rebuttal the rep can say verbatim (1-2 sentences max)",
      "trigger": "string — what in the data suggests this objection: 'techstack', 'news', 'website', 'linkedin'"
    }}
  ],

  "deal_readiness_score": {{
    "score": "integer 1-10",
    "label": "Cold | Warm | Hot",
    "reasoning": "string — 1-2 sentences explaining the score"
  }},

  "data_quality": {{
    "overall": "rich|moderate|sparse",
    "missing_data_warnings": ["string — list any data that was missing or unreliable"]
  }}
}}

---

## STRICT RULES

* Generate EXACTLY 3-4 key_signals

* Generate EXACTLY 3 talking_points

* Generate EXACTLY 2 email_subject_lines

* Generate EXACTLY 2-3 risk_factors

* Generate EXACTLY 2-3 objection_handler items. Base each objection on actual signals in the data — never generic objections like 'too expensive' unless pricing signals exist in the data.

* Generate 1-3 competitor_landscape items. ONLY include competitors you can infer from the actual data (tech stack gaps, job titles, news mentions). If no competitor evidence exists, return an empty array — never fabricate.

* EVERY signal MUST include real evidence

* EVERY talking point must be grounded in signals

* NEVER fabricate missing data

* If data is weak → output becomes simpler, not smarter

---

## FINAL CHECK (MANDATORY)

Before returning JSON:

* Verify: "Can every claim be traced to input data?"
* If NO → remove or downgrade confidence

Return ONLY JSON.
"""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Synthesizer:
    def synthesize(
        self,
        domain: str,
        product_description: str,
        scrape_data: dict,
        news_data: dict,
        tech_data: dict,
        linkedin_data: dict,
    ) -> dict:
        """
        Orchestrates the full synthesis pipeline:
          1. Build structured context string from agent outputs
          2. Call Claude API with system + user prompts
          3. Parse and validate the JSON response
          4. Attach _meta block and return
        """
        context = self._build_context(domain, scrape_data, news_data, tech_data, linkedin_data)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            context=context,
            product_description=product_description,
        )

        # Resolve model + optional base_url from environment
        model = os.getenv("LLM_MODEL", "claude-opus-4-5")
        base_url = os.getenv("LLM_BASE_URL", None)
        
        try:
            from config import get_anthropic_api_key
            api_key = get_anthropic_api_key()
        except (ImportError, EnvironmentError) as e:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY is not set. Please add it to your .env file."
                ) from e

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = anthropic.Anthropic(**client_kwargs)

        try:
            message = client.messages.create(
                model=model,
                max_tokens=4000,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }],
            )
        except Exception as e:
            print(f"FULL ERROR: {type(e).__name__}: {e}")
            raise

        raw = message.content[0].text
        result = self._parse_response(raw)

        result["_meta"] = {
            "domain": domain,
            "model_used": model,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

        return result

    # -----------------------------------------------------------------------
    # Step 1 — Context builder
    # -----------------------------------------------------------------------

    def _build_context(
        self,
        domain: str,
        scrape_data: dict,
        news_data: dict,
        tech_data: dict,
        linkedin_data: dict,
    ) -> str:
        news_lines = "\n".join([
            f"- [{a['category'].upper()}] {a['title']} ({a['date']}) - {a.get('description', '')[:200]}"
            for a in news_data.get("articles", [])[:6]
        ])

        context = f"""
=== COMPANY INTELLIGENCE REPORT FOR {domain.upper()} ===

--- WEBSITE DATA ---
Company Name: {scrape_data.get('company_name', 'Unknown')}
Meta Description: {scrape_data.get('meta_description', 'N/A')}
Homepage Summary: {scrape_data.get('homepage_text', 'N/A')[:1000]}
About Page: {scrape_data.get('about_text', 'N/A')[:500]}
Recent Blog Posts: {', '.join(scrape_data.get('recent_blog_titles', []))}
Funding Mentions on Site: {scrape_data.get('funding_mentions', 'None found')}

--- NEWS (Last 90 Days) ---
Total Articles Found: {news_data.get('total_articles', 0)}
Recent News:
{news_lines}

--- TECH STACK ---
Technologies Detected: {', '.join(tech_data.get('tech_names_flat', ['None detected']))}
Tech Gaps (Missing Tools): {', '.join(tech_data.get('detected_gaps', ['None identified']))}
Has CRM: {tech_data.get('has_crm', False)}
Has Marketing Automation: {tech_data.get('has_marketing_automation', False)}

--- LINKEDIN SIGNALS ---
Employee Count: {linkedin_data.get('employee_count', 'Unknown')}
Headquarters: {linkedin_data.get('headquarters', 'Unknown')}
Founded: {linkedin_data.get('founded_year', 'Unknown')}
Hiring Signal: {linkedin_data.get('hiring_signal', 'Unknown')}
Recent Open Roles: {', '.join(linkedin_data.get('recent_job_titles', ['None found']))}
Growth Indicator: {linkedin_data.get('growth_indicator', 'Unknown')}
"""
        return context

    # -----------------------------------------------------------------------
    # Step 3 — Response parser
    # -----------------------------------------------------------------------

    def _parse_response(self, raw_response: str) -> dict:
        """
        Strip accidental markdown fences and parse the JSON blob.
        Falls back to regex extraction if the model adds preamble text.
        """
        clean = re.sub(r"^```json|```$", "", raw_response.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(
                f"Could not parse Claude response as JSON.\n"
                f"First 500 chars: {raw_response[:500]}"
            )


# ---------------------------------------------------------------------------
# Standalone test — run: python agents/synthesizer.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    # --- Mock data for notion.so ---
    mock_scrape = {
        "domain": "notion.so",
        "company_name": "The AI workspace that works for you. | Notion",
        "meta_description": (
            "Build Custom Agents, search across all your apps, and automate busywork. "
            "The AI workspace where teams get more done, faster."
        ),
        "homepage_text": (
            "Notion agents keep work moving 24/7. They capture knowledge, answer questions, "
            "and push projects forward all while you sleep. Trusted by 98% of the Forbes Cloud 100. "
            "Over 100M users worldwide. #1 knowledge base 3 years running. "
            "62% of Fortune 100. Over 50% of YC companies."
        ),
        "about_text": (
            "Notion started as a simple note-taking tool and evolved into a full workspace platform. "
            "The company is focused on making work tools that combine documents, databases, and AI."
        ),
        "recent_blog_titles": [
            "Enabling Multi-Region Data Systems at Notion",
            "The cure for execution tax",
            "AI features",
        ],
        "funding_mentions": "",
        "scrape_success": True,
    }

    mock_news = {
        "articles": [
            {
                "title": "Notion launches AI connector to link all your work apps",
                "source": "TechCrunch",
                "date": "2026-04-10",
                "description": "Notion announced a new AI-powered connector allowing integrations with Slack, Jira, and Google Drive.",
                "category": "product_launch",
                "url": "https://techcrunch.com/notion-ai-connector",
            },
            {
                "title": "Notion raises $50M Series C at $10B valuation",
                "source": "Bloomberg",
                "date": "2026-03-20",
                "description": "Notion secured $50M in Series C funding led by Sequoia Capital.",
                "category": "funding",
                "url": "https://bloomberg.com/notion-series-c",
            },
        ],
        "funding_news": [],
        "recent_launches": [],
        "total_articles": 2,
        "news_source": "mock",
        "news_success": True,
    }

    mock_tech = {
        "technologies": [{"name": "React", "category": "detected"}],
        "tech_names_flat": ["React"],
        "detected_gaps": [
            "No CRM detected (no Salesforce, HubSpot, Pipedrive)",
            "No marketing automation (no Marketo, Pardot, ActiveCampaign)",
        ],
        "has_crm": False,
        "has_marketing_automation": False,
        "has_analytics": False,
        "has_support_tool": False,
        "tech_source": "html_scan_fallback",
        "tech_success": True,
    }

    mock_linkedin = {
        "employee_count": "1001-5000",
        "follower_count": 250000,
        "headquarters": "San Francisco, CA",
        "founded_year": "2016",
        "specialties": ["productivity", "knowledge management", "AI", "collaboration"],
        "recent_job_titles": [
            "Senior Enterprise Account Executive",
            "Head of Revenue Operations",
            "Staff ML Engineer",
        ],
        "hiring_signal": "actively_hiring",
        "growth_indicator": "scaling_leadership",
        "linkedin_source": "mock",
        "linkedin_success": True,
    }

    console.print("[bold cyan]Running Synthesizer with mock Notion data...[/bold cyan]\n")

    try:
        synth = Synthesizer()
        result = synth.synthesize(
            domain="notion.so",
            product_description="AI workflow automation platform for ops teams — automates repetitive processes, connects siloed tools, and surfaces execution gaps in real time.",
            scrape_data=mock_scrape,
            news_data=mock_news,
            tech_data=mock_tech,
            linkedin_data=mock_linkedin,
        )
        console.print(
            Panel(
                json.dumps(result, indent=2),
                title="[green]Synthesizer Output[/green]",
                expand=False,
            )
        )
    except EnvironmentError as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]Synthesis failed:[/bold red] {e}")
