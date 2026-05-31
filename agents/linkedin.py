"""
agents/linkedin.py — LinkedIn Signal Agent (LinkdAPI)
Primary: LinkdAPI (100 free credits, no card required → linkdapi.com/signup)
Fallback: Returns graceful empty state with clear warning
"""

import os
import re
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()


class LinkedInAgent:
    def get_signals(self, company_name: str, domain: str) -> dict:
        try:
            from config import get_linkdapi_api_key
            api_key = get_linkdapi_api_key()
        except ImportError:
            api_key = os.getenv("LINKDAPI_API_KEY") or os.getenv("LINKDAPI_KEY", "")

        if not api_key:
            return self._graceful_empty("LINKDAPI_KEY not set")

        from linkdapi import LinkdAPI
        client = LinkdAPI(api_key)

        domain_prefix = domain.split('.')[0] if domain else ""
        domain_no_tld = '-'.join(domain.split('.')[:-1]) if domain else ""
        company_slug = re.sub(r'[^a-z0-9]+', '-', company_name.lower()).strip('-')

        slugs = []
        for s in [domain_prefix, domain_no_tld, company_slug]:
            if s and s not in slugs:
                slugs.append(s)

        for slug in slugs:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._process_slug, client, slug)
                    result = future.result(timeout=8)
                
                if result is not None:
                    return result
            except concurrent.futures.TimeoutError as e:
                print(f"LinkedIn lookup failed for {slug}: TimeoutError")
                return self._graceful_empty("TimeoutError")
            except Exception as e:
                print(f"LinkedIn lookup failed for {slug}: {e}")
                return self._graceful_empty(str(e))

        return self._graceful_empty("No matching company found for any slug")

    def _process_slug(self, client, slug: str):
        try:
            search_result = client.company_name_lookup(slug)
        except Exception as e:
            print(f"LinkedIn lookup failed for {slug}: {e}")
            return self._graceful_empty(str(e))

        companies = search_result.get("data", []) if isinstance(search_result, dict) else []
        if not companies:
            return None

        company = companies[0]
        company_id = company.get("id") or company.get("companyId")
        if not company_id:
            return None

        try:
            info_res = client.get_company_info(company_id=company_id)
            info = info_res.get("data", {}) if isinstance(info_res, dict) else {}
        except Exception as e:
            print(f"LinkedIn lookup failed for {slug}: {e}")
            return self._graceful_empty(str(e))

        try:
            emp_res = client.get_company_employees_data(company_id)
            emp_data = emp_res.get("data", {}) if isinstance(emp_res, dict) else {}
        except Exception as e:
            print(f"LinkedIn lookup failed for {slug}: {e}")
            return self._graceful_empty(str(e))

        try:
            jobs_res = client.get_company_jobs(company_id)
            jobs_data = jobs_res.get("data", {}) if isinstance(jobs_res, dict) else {}
            job_list = jobs_data if isinstance(jobs_data, list) else []
            recent_job_titles = [j.get("title", "") for j in job_list[:5] if j.get("title")]
        except Exception as e:
            print(f"LinkedIn lookup failed for {slug}: {e}")
            return self._graceful_empty(str(e))

        employee_count = (
            str(info.get("employeeCount", ""))
            or str(emp_data.get("totalEmployees", ""))
            or "unknown"
        )
        hq = info.get("headquarters", {}) or {}
        headquarters = ", ".join(
            filter(None, [hq.get("city"), hq.get("geographicArea"), hq.get("country")])
        )
        founded_year = str(info.get("foundedOn", {}).get("year", "") or "")

        hiring_signal = self._infer_hiring_signal(recent_job_titles)
        growth_indicator = self._infer_growth(recent_job_titles, employee_count)

        return {
            "employee_count": employee_count,
            "headquarters": headquarters,
            "founded_year": founded_year,
            "hiring_signal": hiring_signal,
            "recent_job_titles": recent_job_titles,
            "growth_indicator": growth_indicator,
            "linkedin_success": True,
            "error": ""
        }

    def _graceful_empty(self, error: str) -> dict:
        return {
            "employee_count": "unknown",
            "headquarters": "unknown", 
            "founded_year": "unknown",
            "hiring_signal": "unknown",
            "recent_job_titles": [],
            "growth_indicator": "unknown",
            "linkedin_success": False,
            "error": error
        }

    @staticmethod
    def _infer_hiring_signal(job_titles: list) -> str:
        count = len(job_titles)
        if count >= 4:
            return "actively_hiring"
        if count >= 2:
            return "moderate"
        return "unknown"

    @staticmethod
    def _infer_growth(job_titles: list, employee_count: str) -> str:
        growth_kws = ["senior", "lead", "head", "director", "vp", "principal"]
        leadership_roles = sum(
            1 for t in job_titles if any(k in t.lower() for k in growth_kws)
        )
        if leadership_roles >= 2:
            return "scaling_leadership"
        if len(job_titles) >= 3:
            return "growing"
        return "stable_or_unknown"
