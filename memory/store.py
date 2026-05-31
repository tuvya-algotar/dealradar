import sqlite3
import json
import os
from datetime import datetime

class MemoryStore:
    def __init__(self, db_path="cache/dealradar_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                researched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                brief_json TEXT NOT NULL,
                scrape_data_json TEXT,
                news_data_json TEXT,
                tech_data_json TEXT,
                linkedin_data_json TEXT,
                deal_readiness_score INTEGER,
                deal_readiness_label TEXT
            )
            """)
            try:
                cursor.execute("ALTER TABLE research_history ADD COLUMN jobs_data_json TEXT")
            except sqlite3.OperationalError:
                pass
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_diffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                diff_generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                previous_research_id INTEGER,
                current_research_id INTEGER,
                diff_json TEXT NOT NULL,
                days_between INTEGER,
                FOREIGN KEY (previous_research_id) REFERENCES research_history(id),
                FOREIGN KEY (current_research_id) REFERENCES research_history(id)
            )
            """)
            conn.commit()

    def save_research(self, domain: str, brief_data: dict, scrape_data: dict, news_data: dict, tech_data: dict, linkedin_data: dict, jobs_data: dict = None) -> int:
        previous_research = self.get_previous_research(domain)
        
        deal_score = brief_data.get("deal_readiness_score", {}).get("score", 0)
        deal_label = brief_data.get("deal_readiness_score", {}).get("label", "")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO research_history (
                domain, brief_json, scrape_data_json, news_data_json, tech_data_json, linkedin_data_json, jobs_data_json, deal_readiness_score, deal_readiness_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                domain,
                json.dumps(brief_data),
                json.dumps(scrape_data) if scrape_data else None,
                json.dumps(news_data) if news_data else None,
                json.dumps(tech_data) if tech_data else None,
                json.dumps(linkedin_data) if linkedin_data else None,
                json.dumps(jobs_data) if jobs_data else None,
                deal_score,
                deal_label
            ))
            current_id = cursor.lastrowid
            conn.commit()

        if previous_research:
            previous_id = previous_research["id"]
            previous_brief = previous_research["brief_data"]
            self._generate_diff(domain, previous_id, current_id, previous_brief, brief_data)
            
        return current_id

    def get_previous_research(self, domain: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM research_history
            WHERE domain = ?
            ORDER BY researched_at DESC
            LIMIT 1
            """, (domain,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return {
                "id": row["id"],
                "domain": row["domain"],
                "researched_at": row["researched_at"],
                "brief_data": json.loads(row["brief_json"]),
                "scrape_data": json.loads(row["scrape_data_json"]) if row["scrape_data_json"] else None,
                "news_data": json.loads(row["news_data_json"]) if row["news_data_json"] else None,
                "tech_data": json.loads(row["tech_data_json"]) if row["tech_data_json"] else None,
                "linkedin_data": json.loads(row["linkedin_data_json"]) if row["linkedin_data_json"] else None,
                "deal_readiness_score": row["deal_readiness_score"],
                "deal_readiness_label": row["deal_readiness_label"]
            }

    def _generate_diff(self, domain: str, previous_id: int, current_id: int, previous_brief: dict, current_brief: dict) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT researched_at FROM research_history WHERE id = ?", (previous_id,))
            prev_time_str = cursor.fetchone()[0]
            cursor.execute("SELECT researched_at FROM research_history WHERE id = ?", (current_id,))
            curr_time_str = cursor.fetchone()[0]
            
            def _parse_sqlite_dt(s: str) -> datetime:
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        continue
                raise ValueError(f"Unrecognised datetime format: {s}")

            prev_time = _parse_sqlite_dt(prev_time_str)
            curr_time = _parse_sqlite_dt(curr_time_str)
            days_between = (curr_time - prev_time).days
        
        prev_score = previous_brief.get("deal_readiness_score", {}).get("score", 0)
        curr_score = current_brief.get("deal_readiness_score", {}).get("score", 0)
        delta = curr_score - prev_score
        direction = "unchanged"
        if delta > 0:
            direction = "improved"
        elif delta < 0:
            direction = "declined"
            
        deal_score_change = {
            "previous": prev_score,
            "current": curr_score,
            "delta": delta,
            "direction": direction
        }
        
        prev_signals = {s.get("signal"): s.get("source") for s in previous_brief.get("key_signals", [])}
        curr_signals = {s.get("signal"): s.get("source") for s in current_brief.get("key_signals", [])}
        
        new_signals = [{"signal": s, "source": curr_signals[s]} for s in curr_signals if s not in prev_signals]
        dropped_signals = [{"signal": s, "source": prev_signals[s]} for s in prev_signals if s not in curr_signals]
        
        prev_risks = set(previous_brief.get("risk_factors", []))
        curr_risks = set(current_brief.get("risk_factors", []))
        new_risks = list(curr_risks - prev_risks)
        resolved_risks = list(prev_risks - curr_risks)
        
        prev_tps = len(previous_brief.get("talking_points", []))
        curr_tps = len(current_brief.get("talking_points", []))
        if curr_tps > prev_tps:
            tp_changes = f"Added {curr_tps - prev_tps} new talking points."
        elif curr_tps < prev_tps:
            tp_changes = f"Removed {prev_tps - curr_tps} talking points."
        else:
            tp_changes = "Talking points were updated but count remains the same."

        summary_parts = []
        if direction != "unchanged":
            summary_parts.append(f"Deal score {direction} from {prev_score} to {curr_score}.")
        if new_signals:
            summary_parts.append(f"Detected {len(new_signals)} new signals.")
        if resolved_risks:
            summary_parts.append(f"Resolved {len(resolved_risks)} previous risks.")
            
        summary = " ".join(summary_parts) if summary_parts else "No significant changes detected since last research."
        
        diff = {
            "domain": domain,
            "days_between": days_between,
            "deal_score_change": deal_score_change,
            "new_signals": new_signals,
            "dropped_signals": dropped_signals,
            "talking_point_changes": tp_changes,
            "new_risks": new_risks,
            "resolved_risks": resolved_risks,
            "summary": summary
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO intelligence_diffs (
                domain, previous_research_id, current_research_id, diff_json, days_between
            ) VALUES (?, ?, ?, ?, ?)
            """, (domain, previous_id, current_id, json.dumps(diff), days_between))
            conn.commit()
            
        return diff

    def get_diff_history(self, domain: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM intelligence_diffs
            WHERE domain = ?
            ORDER BY diff_generated_at DESC
            """, (domain,))
            rows = cursor.fetchall()
            return [json.loads(row["diff_json"]) for row in rows]

    def has_previous_research(self, domain: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 1 FROM research_history
            WHERE domain = ?
            LIMIT 1
            """, (domain,))
            return cursor.fetchone() is not None

    def get_research_timeline(self, domain: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, researched_at, deal_readiness_score, deal_readiness_label
            FROM research_history
            WHERE domain = ?
            ORDER BY researched_at ASC
            """, (domain,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_briefs_for_domain(self, domain: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT id, researched_at, deal_readiness_score, deal_readiness_label, brief_json, jobs_data_json
                    FROM research_history
                    WHERE domain = ?
                    ORDER BY researched_at DESC
                """, (domain,))
                rows = cursor.fetchall()
                return [{
                    "id": row["id"],
                    "researched_at": row["researched_at"],
                    "score": row["deal_readiness_score"],
                    "label": row["deal_readiness_label"],
                    "brief_data": json.loads(row["brief_json"]),
                    "jobs_data": json.loads(row["jobs_data_json"]) if row["jobs_data_json"] else {}
                } for row in rows]
            except sqlite3.OperationalError:
                # If jobs_data_json column is missing for some reason
                cursor.execute("""
                    SELECT id, researched_at, deal_readiness_score, deal_readiness_label, brief_json
                    FROM research_history
                    WHERE domain = ?
                    ORDER BY researched_at DESC
                """, (domain,))
                rows = cursor.fetchall()
                return [{
                    "id": row["id"],
                    "researched_at": row["researched_at"],
                    "score": row["deal_readiness_score"],
                    "label": row["deal_readiness_label"],
                    "brief_data": json.loads(row["brief_json"]),
                    "jobs_data": {}
                } for row in rows]

    def get_score_history(self, domain: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT deal_readiness_score, researched_at
                FROM research_history
                WHERE domain = ? AND deal_readiness_score IS NOT NULL
                ORDER BY researched_at ASC
            """, (domain,))
            return [{"score": r[0], "date": r[1][:10]} for r in cursor.fetchall()]

if __name__ == "__main__":
    store = MemoryStore("cache/test_memory.db")
    
    mock_brief_1 = {
        "deal_readiness_score": {"score": 6, "label": "Warm"},
        "key_signals": [{"signal": "Hiring Engineers", "source": "linkedin"}],
        "risk_factors": ["High competition", "Low cash runway"],
        "talking_points": [{"point": "How's engineering growth?"}]
    }
    
    store.save_research("notion.so", mock_brief_1, {}, {}, {}, {})
    
    mock_brief_2 = {
        "deal_readiness_score": {"score": 8, "label": "Hot"},
        "key_signals": [
            {"signal": "Hiring Engineers", "source": "linkedin"},
            {"signal": "Launch AI features", "source": "news"}
        ],
        "risk_factors": ["High competition"],
        "talking_points": [{"point": "How's engineering growth?"}, {"point": "AI strategy?"}]
    }
    
    store.save_research("notion.so", mock_brief_2, {}, {}, {}, {})
    
    diffs = store.get_diff_history("notion.so")
    print("Generated Diff:")
    print(json.dumps(diffs[0], indent=2) if diffs else "No diff generated")
    
    timeline = store.get_research_timeline("notion.so")
    print("\nResearch Timeline:")
    print(json.dumps(timeline, indent=2))
