from jinja2 import Environment, FileSystemLoader
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    HTML = None
    WEASYPRINT_AVAILABLE = False
from datetime import datetime
import os

class PDFRenderer:
    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def render(self, brief_data: dict, domain: str, output_path: str) -> str:
        """
        Takes synthesized brief_data dict, renders to PDF.
        Returns the path to the generated PDF.
        """
        template = self.env.get_template('brief.html')
        
        # Ensure all required keys exist to prevent Jinja UndefinedError
        brief_data = brief_data.copy() if brief_data else {}
        brief_data.setdefault('company_name', domain.split('.')[0].title())
        brief_data.setdefault('company_snapshot', 'No snapshot available.')
        brief_data.setdefault('deal_readiness_score', {'score': 0, 'label': 'Unknown', 'reasoning': 'Not enough data.'})
        brief_data.setdefault('key_signals', [])
        brief_data.setdefault('talking_points', [])
        brief_data.setdefault('email_subject_lines', [])
        brief_data.setdefault('best_persona_to_target', {'title': 'Unknown Persona', 'why': 'Insufficient data to determine.'})
        brief_data.setdefault('risk_factors', [])
        brief_data.setdefault('data_quality', {'missing_data_warnings': []})
        
        html_content = template.render(
            brief=brief_data,
            domain=domain,
            generated_date=datetime.now().strftime("%B %d, %Y at %I:%M %p")
        )
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if WEASYPRINT_AVAILABLE:
            HTML(string=html_content).write_pdf(output_path)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print("WARNING: GTK+ dependencies missing for weasyprint. Saved raw HTML instead of PDF.")
        return output_path

    def render_html(self, brief_data: dict, domain: str) -> str:
        """Returns rendered HTML string (for Streamlit preview)"""
        template = self.env.get_template('brief.html')
        return template.render(
            brief=brief_data,
            domain=domain,
            generated_date=datetime.now().strftime("%B %d, %Y at %I:%M %p")
        )

if __name__ == "__main__":
    mock_brief_data = {
        "company_name": "Notion",
        "company_snapshot": "Notion is an all-in-one workspace that combines notes, docs, project management, and wikis into a single highly customizable platform. It is widely adopted by startups and enterprise teams to streamline collaboration and centralize company knowledge.",
        "deal_readiness_score": {
            "score": 8,
            "label": "Hot",
            "reasoning": "Recent funding, expanding enterprise features, and strong hiring in product roles indicate readiness for sophisticated tooling."
        },
        "key_signals": [
            {
                "signal": "Hiring 20+ Enterprise Account Executives",
                "implication": "Pushing heavily into upmarket/enterprise sales, likely need better training and enablement tooling.",
                "source": "linkedin",
                "confidence": "high",
                "confidence_reason": "Directly from Notion's career page"
            },
            {
                "signal": "Launch of 'Notion AI' integration",
                "implication": "Investing in AI-powered productivity, strong alignment for AI-related value propositions.",
                "source": "news",
                "confidence": "high",
                "confidence_reason": "Recent major press release"
            },
            {
                "signal": "Expanding presence in EMEA",
                "implication": "Scaling global operations, potentially facing localization and cross-region collaboration challenges.",
                "source": "news",
                "confidence": "medium",
                "confidence_reason": "Mentioned in recent tech blogs"
            }
        ],
        "talking_points": [
            {
                "point": "How are your new Enterprise AEs scaling their outreach and enablement?",
                "why_it_works": "Ties into their recent massive hiring push and addresses common scaling pain points.",
                "confidence": "high",
                "confidence_reason": "High relevance to hiring signal"
            },
            {
                "point": "With the push into EMEA, how are you ensuring consistent messaging across regions?",
                "why_it_works": "Connects regional expansion with enablement and consistency challenges.",
                "confidence": "medium",
                "confidence_reason": "Logical deduction from expansion news"
            }
        ],
        "email_subject_lines": [
            {
                "subject": "Scaling Enterprise AEs at Notion",
                "approach": "Direct & Contextual"
            },
            {
                "subject": "Notion AI + Enablement Stack",
                "approach": "Value & Tech alignment"
            }
        ],
        "best_persona_to_target": {
            "title": "VP of Revenue Operations / Head of Sales Enablement",
            "why": "They are responsible for onboarding the new Enterprise AEs and ensuring ROI on sales tooling."
        },
        "risk_factors": [
            "Highly competitive tooling space; they may prefer building internal solutions using Notion.",
            "Long enterprise sales cycles and procurement processes."
        ],
        "data_quality": {
            "missing_data_warnings": ["Exact tech stack budget", "Recent churn metrics"]
        }
    }

    renderer = PDFRenderer()
    
    # Get project root assuming output/renderer.py
    project_root = os.path.dirname(os.path.dirname(__file__))
    output_pdf_path = os.path.join(project_root, "reports", "test_brief.pdf")
    
    print(f"Generating PDF report to {output_pdf_path}...")
    pdf_path = renderer.render(mock_brief_data, "notion.so", output_pdf_path)
    print(f"PDF successfully generated at: {pdf_path}")
