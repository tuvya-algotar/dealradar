"""
agents/techstack.py — Tech Stack Agent
Detects technologies used by a company website.
Primary: BuiltWith API    Fallback: HTML source pattern scan
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BUILTWITH_API_URL = (
    "https://api.builtwith.com/free1/api.json?KEY={key}&LOOKUP={domain}"
)

TECH_SIGNATURES: dict[str, list[str]] = {
    "React": ["react.js", "react.min.js", "_next/", "/__next"],
    "Vue.js": ["vue.js", "vue.min.js", "nuxt"],
    "Angular": ["angular.js", "ng-version"],
    "Salesforce": ["salesforce.com", "force.com", "pardot"],
    "HubSpot": ["hubspot.com", "hs-scripts", "hbspt"],
    "Intercom": ["intercom.io", "widget.intercom.io"],
    "Stripe": ["stripe.com/v3", "js.stripe.com"],
    "Segment": ["segment.com", "analytics.js"],
    "Zendesk": ["zendesk.com", "zopim"],
    "Marketo": ["marketo.net", "munchkin.js"],
    "Google Analytics": ["google-analytics.com", "gtag/js"],
    "Hotjar": ["hotjar.com"],
    "WordPress": ["wp-content", "wp-includes"],
    "Shopify": ["shopify.com", "cdn.shopify"],
    "AWS": ["amazonaws.com", "cloudfront.net"],
    "Cloudflare": ["cloudflare.com", "__cfduid"],
    "Mixpanel": ["mixpanel.com"],
    "Amplitude": ["amplitude.com"],
    "ActiveCampaign": ["activecampaign.com"],
    "Pipedrive": ["pipedrive.com"],
    "Freshdesk": ["freshdesk.com", "freshworks.com"],
}

CRM_TECHS = {"Salesforce", "HubSpot", "Pipedrive"}
MARKETING_TECHS = {"Marketo", "ActiveCampaign", "Salesforce"}  # Pardot ⊆ Salesforce
ANALYTICS_TECHS = {"Google Analytics", "Mixpanel", "Amplitude", "Segment"}
SUPPORT_TECHS = {"Intercom", "Zendesk", "Freshdesk"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


class TechStackAgent:
    def get_techstack(self, domain: str) -> dict:
        """
        Try BuiltWith API first, fall back to HTML scan.
        Never raises.
        """
        try:
            from config import get_builtwith_api_key
            api_key = get_builtwith_api_key()
        except ImportError:
            api_key = os.getenv("BUILTWITH_API_KEY", "")

        if api_key:
            try:
                return self._fetch_builtwith(domain, api_key)
            except Exception:
                pass  # fall through

        try:
            return self._html_scan(domain)
        except Exception as e:
            return {
                "technologies": [],
                "tech_names_flat": [],
                "detected_gaps": [],
                "has_crm": False,
                "has_marketing_automation": False,
                "has_analytics": False,
                "has_support_tool": False,
                "tech_source": "none",
                "tech_success": False,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Primary: BuiltWith API
    # ------------------------------------------------------------------

    def _fetch_builtwith(self, domain: str, api_key: str) -> dict:
        url = BUILTWITH_API_URL.format(key=api_key, domain=domain)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        technologies = []
        try:
            paths = data["Results"][0]["Result"]["Paths"]
            for path in paths:
                for tech in path.get("Technologies", []):
                    name = tech.get("Name", "")
                    tag = tech.get("Tag", "")
                    if name:
                        technologies.append({"name": name, "category": tag})
        except (KeyError, IndexError, TypeError):
            raise ValueError("Unexpected BuiltWith response structure")

        return self._build_result(technologies, source="builtwith")

    # ------------------------------------------------------------------
    # Fallback: HTML pattern scan
    # ------------------------------------------------------------------

    def _html_scan(self, domain: str) -> dict:
        base = domain if domain.startswith("http") else f"https://{domain}"
        resp = requests.get(base, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        html_lower = resp.text.lower()

        technologies = []
        for tech_name, signatures in TECH_SIGNATURES.items():
            if any(sig.lower() in html_lower for sig in signatures):
                technologies.append({"name": tech_name, "category": "detected"})

        return self._build_result(technologies, source="html_scan_fallback")

    # ------------------------------------------------------------------
    # Shared: gap analysis + result builder
    # ------------------------------------------------------------------

    def _build_result(self, technologies: list, source: str) -> dict:
        tech_names = {t["name"] for t in technologies}
        flat_list = list(tech_names)

        has_crm = bool(tech_names & CRM_TECHS)
        has_marketing = bool(tech_names & MARKETING_TECHS)
        has_analytics = bool(tech_names & ANALYTICS_TECHS)
        has_support = bool(tech_names & SUPPORT_TECHS)

        gaps = []
        if not has_crm:
            gaps.append("No CRM detected (no Salesforce, HubSpot, Pipedrive)")
        if not has_marketing:
            gaps.append("No marketing automation (no Marketo, Pardot, ActiveCampaign)")
        if not has_analytics:
            gaps.append("No analytics (no Google Analytics, Mixpanel, Amplitude)")
        if not has_support:
            gaps.append("No customer support tool (no Intercom, Zendesk, Freshdesk)")

        return {
            "technologies": technologies,
            "tech_names_flat": flat_list,
            "detected_gaps": gaps,
            "has_crm": has_crm,
            "has_marketing_automation": has_marketing,
            "has_analytics": has_analytics,
            "has_support_tool": has_support,
            "tech_source": source,
            "tech_success": True,
        }
