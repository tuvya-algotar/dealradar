import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

class JobsAgent:
    def get_job_signals(self, domain: str) -> dict:
        company = domain.split(".")[0]
        results = {"jobs": [], "job_count": 0, "hiring_themes": [], "jobs_success": False}
        
        # Try Indeed RSS (free, no key)
        try:
            rss_url = f"https://www.indeed.com/rss?q={company}&sort=date&limit=10"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(rss_url, headers=headers, timeout=8)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                cutoff = datetime.now() - timedelta(days=60)
                for item in root.findall(".//item")[:10]:
                    title = item.findtext("title","")
                    pub_date_str = item.findtext("pubDate","")
                    try:
                        pub_date = datetime.strptime(pub_date_str[:16], "%a, %d %b %Y")
                        if pub_date < cutoff:
                            continue
                    except:
                        pass
                    results["jobs"].append({"title": title, "date": pub_date_str[:16]})
                results["job_count"] = len(results["jobs"])
                results["jobs_success"] = True
        except Exception as e:
            results["error"] = str(e)
        
        # Derive hiring themes from job titles
        titles_text = " ".join([j["title"].lower() for j in results["jobs"]])
        themes = []
        if any(w in titles_text for w in ["engineer","developer","sre","devops"]): themes.append("engineering growth")
        if any(w in titles_text for w in ["sales","account exec","ae","sdr","bdr"]): themes.append("sales expansion")
        if any(w in titles_text for w in ["data","ml","ai","machine learning"]): themes.append("AI/data investment")
        if any(w in titles_text for w in ["ops","operations","finance","legal"]): themes.append("operational scaling")
        if any(w in titles_text for w in ["marketing","growth","content","brand"]): themes.append("marketing push")
        results["hiring_themes"] = themes
        
        return results
