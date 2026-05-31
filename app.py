import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import streamlit as st
import time
import os
import sqlite3
import streamlit.components.v1 as components
from main import run_pipeline
from memory.store import MemoryStore
from output.renderer import PDFRenderer

# --- PAGE CONFIG ---
st.set_page_config(page_title="DealRadar", page_icon="🎯", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

.stApp { background-color: #0d0d14; }
* { font-family: 'Inter', sans-serif; }

/* Fix ALL invisible text */
.stMarkdown p, .stMarkdown li { color: #e2e0f0 !important; }
.stAlert p { color: #e2e0f0 !important; }
.stExpander p { color: #e2e0f0 !important; }
div[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 2rem !important; font-weight: 600 !important; }
div[data-testid="stMetricLabel"] { color: #7c7a9a !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.08em; }
div[data-testid="stMetricDelta"] { color: #10b981 !important; }
.streamlit-expanderContent { color: #e2e0f0 !important; }
h1, h2, h3 { color: #ffffff !important; font-weight: 600 !important; }

/* Sidebar */
[data-testid="stSidebar"] { background-color: #0a0a10 !important; border-right: 1px solid #1e1c2e; }
[data-testid="stSidebar"] * { color: #e2e0f0 !important; }
[data-testid="stSidebar"] .stButton > button { background: transparent !important; color: #7c7a9a !important; border: 1px solid #2a2840 !important; text-align: left; padding: 0.35rem 0.75rem; width: 100%; font-size: 0.82rem; border-radius: 6px; margin-bottom: 4px; }
[data-testid="stSidebar"] .stButton > button:hover { background: #1a1828 !important; color: #e2e0f0 !important; border-color: #7c3aed !important; }

/* Cards / containers */
div[data-testid="stExpander"] { background: #12121e !important; border: 1px solid #1e1c2e !important; border-radius: 10px; }
div[data-testid="column"] { gap: 1rem; }

/* Metric cards — override streamlit default */
div[data-testid="metric-container"] { background: #12121e; border: 1px solid #1e1c2e; border-radius: 10px; padding: 1.25rem 1.5rem; }

/* Tabs */
button[data-baseweb="tab"] { color: #7c7a9a !important; font-size: 0.9rem; }
button[data-baseweb="tab"][aria-selected="true"] { color: #ffffff !important; border-bottom: 2px solid #7c3aed !important; }
div[data-testid="stTabs"] > div:first-child { border-bottom: 1px solid #1e1c2e !important; margin-bottom: 1rem; }

/* Primary button */
div.stButton > button:first-child { background: #7c3aed !important; color: white !important; font-weight: 600; border: none; border-radius: 8px; padding: 0.6rem 1.2rem; transition: 0.2s; }
div.stButton > button:first-child:hover { background: #6d28d9 !important; }

/* Download button */
div.stDownloadButton > button { background: #12121e !important; color: #e2e0f0 !important; border: 1px solid #7c3aed !important; border-radius: 8px; font-weight: 500; }

/* Text inputs */
.stTextInput input, .stTextArea textarea { background: #12121e !important; color: #e2e0f0 !important; border: 1px solid #2a2840 !important; border-radius: 8px; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: #7c3aed !important; box-shadow: 0 0 0 2px rgba(124,58,237,0.2) !important; }

/* Status widget */
div[data-testid="stStatusWidget"] { background: #12121e !important; border: 1px solid #7c3aed !important; border-radius: 8px; }

/* Alerts */
div[data-testid="stAlert"] { border-radius: 8px; background: #12121e !important; }
div[data-testid="stAlert"][data-type="warning"] { border-left: 3px solid #f59e0b !important; }
div[data-testid="stAlert"][data-type="error"] { border-left: 3px solid #ef4444 !important; }
div[data-testid="stAlert"][data-type="info"] { border-left: 3px solid #7c3aed !important; }

/* Dataframe */
div[data-testid="stDataFrame"] { border: 1px solid #1e1c2e; border-radius: 8px; overflow: hidden; }
</style>""", unsafe_allow_html=True)

# --- INIT STATE ---
if "domain_input" not in st.session_state:
    st.session_state.domain_input = ""

memory = MemoryStore()

def fetch_recent_briefs():
    try:
        with sqlite3.connect(memory.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT domain FROM research_history ORDER BY researched_at DESC LIMIT 5")
            return [r[0] for r in cursor.fetchall()]
    except Exception:
        return []

def get_total_briefs():
    try:
        with sqlite3.connect(memory.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM research_history")
            return cursor.fetchone()[0]
    except Exception:
        return 0

recent_domains = fetch_recent_briefs()
total_briefs = get_total_briefs()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0 1.5rem;">
        <div style="font-size: 1.4rem; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">
            🎯 DealRadar
        </div>
        <div style="font-size: 0.75rem; color: #7c7a9a; margin-top: 2px;">AI Sales Intelligence</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="font-size:0.68rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Recent Briefs</div>', unsafe_allow_html=True)
    for d in recent_domains:
        score_history = memory.get_score_history(d)
        scores = [s["score"] for s in score_history]
        
        # Build dot indicators (last 5 runs max)
        dots_html = ""
        for sc in scores[-5:]:
            dot_color = "#10b981" if sc >= 7 else "#f59e0b" if sc >= 4 else "#ef4444"
            dots_html += f'<span style="width:6px;height:6px;border-radius:50%;background:{dot_color};display:inline-block;margin-right:2px;"></span>'
        
        latest_score = scores[-1] if scores else "?"
        score_color = "#10b981" if latest_score != "?" and latest_score >= 7 else "#f59e0b" if latest_score != "?" and latest_score >= 4 else "#7c7a9a"
        
        col_btn, col_score = st.columns([3,1])
        with col_btn:
            if st.button(d, key=f"btn_{d}"):
                st.session_state.domain_input = d
        with col_score:
            st.markdown(f'''<div style="display:flex;align-items:center;gap:4px;padding-top:6px;">
                {dots_html}
                <span style="font-size:0.7rem;color:{score_color};font-weight:600;">{latest_score}</span>
            </div>''', unsafe_allow_html=True)
            
    if st.session_state.get("domain_input"):
        d = st.session_state["domain_input"]
        history = memory.get_all_briefs_for_domain(d)
        if len(history) > 1:
            st.markdown('<div style="font-size:0.68rem;color:#4a4864;margin-top:8px;">Past runs for this domain:</div>', unsafe_allow_html=True)
            for h in history[1:]:
                label_color = "#10b981" if h["label"]=="Hot" else "#f59e0b" if h["label"]=="Warm" else "#7c7a9a"
                btn_label = f"{h['researched_at'][:10]} · {h['score']}/10"
                if st.button(btn_label, key=f"hist_{h['id']}"):
                    st.session_state["viewing_historical"] = h["brief_data"]
                    st.session_state["viewing_historical_date"] = h["researched_at"]
                    st.session_state["viewing_historical_jobs"] = h.get("jobs_data", {})
    
    st.markdown('<hr style="border-color: #1e1c2e; margin: 1.5rem 0;">', unsafe_allow_html=True)
    
    # Stats from SQLite (already computed: total_briefs, recent_domains)
    st.markdown(f"""
    <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.75rem;">
        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;">Total Briefs</div>
        <div style="font-size:1.8rem;font-weight:600;color:#ffffff;margin-top:2px;">{total_briefs}</div>
    </div>
    <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1rem 1.25rem;">
        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;">Companies Tracked</div>
        <div style="font-size:1.8rem;font-weight:600;color:#ffffff;margin-top:2px;">{len(recent_domains)}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="margin-top:2rem;font-size:0.7rem;color:#4a4864;padding:0.5rem 0;">Powered by Claude</div>', unsafe_allow_html=True)

def render_brief_tab(brief_data, domain, jobs_data={}):
    # Build plain text version of brief
    def build_plain_text_brief(brief_data, domain):
        lines = []
        lines.append(f"DEALRADAR PRE-CALL BRIEF — {domain.upper()}")
        lines.append("=" * 60)
        score = brief_data.get("deal_readiness_score", {})
        lines.append(f"Deal Score: {score.get('score')}/10 ({score.get('label')})")
        lines.append(f"Reasoning: {score.get('reasoning','')}")
        lines.append("")
        lines.append("COMPANY SNAPSHOT")
        lines.append(brief_data.get("company_snapshot",""))
        lines.append("")
        lines.append("KEY SIGNALS")
        for s in brief_data.get("key_signals",[]):
            lines.append(f"• [{s.get('confidence','').upper()}] {s.get('signal')} ({s.get('source')})")
            lines.append(f"  → {s.get('implication')}")
        lines.append("")
        lines.append("TALKING POINTS")
        for i,tp in enumerate(brief_data.get("talking_points",[]),1):
            lines.append(f"{i}. {tp.get('point')}")
            lines.append(f"   Why it works: {tp.get('why_it_works')}")
        lines.append("")
        lines.append("EMAIL SUBJECTS")
        for e in brief_data.get("email_subject_lines",[]):
            lines.append(f"• {e.get('subject')} [{e.get('approach')}]")
        lines.append("")
        lines.append("BEST PERSONA")
        p = brief_data.get("best_persona_to_target",{})
        lines.append(f"{p.get('title','')} — {p.get('why','')}")
        lines.append("")
        lines.append("RISK FACTORS")
        for r in brief_data.get("risk_factors",[]):
            lines.append(f"• {r}")
        return "\n".join(lines)
    
    plain_text = build_plain_text_brief(brief_data, domain)
    
    # Show copy button using st.code so user can manually copy, plus a download button
    col_copy1, col_copy2, col_copy3 = st.columns([1,1,4])
    with col_copy1:
        st.download_button(
            "Download .txt",
            data=plain_text,
            file_name=f"{domain.replace('.','_')}_brief.txt",
            mime="text/plain",
            use_container_width=True
        )
    with col_copy2:
        with st.expander("View raw text"):
            st.code(plain_text, language=None)

    score = brief_data.get("deal_readiness_score", {}).get("score", "?")
    label = brief_data.get("deal_readiness_score", {}).get("label", "Unknown")
    reasoning = brief_data.get("deal_readiness_score", {}).get("reasoning", "")
    score_color = "#10b981" if label == "Hot" else "#f59e0b" if label == "Warm" else "#7c7a9a"
    badge_bg = "#052e16" if label == "Hot" else "#2d1f00" if label == "Warm" else "#1a1a2e"
    company_name = brief_data.get("company_name", domain)
    data_quality = brief_data.get("data_quality", {}).get("overall", "unknown")
    dq_color = "#10b981" if data_quality == "rich" else "#f59e0b" if data_quality == "moderate" else "#ef4444"
    
    st.markdown(f"""
    <div style="display:flex;gap:16px;margin-bottom:1.5rem;flex-wrap:wrap;">
        <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:12px;padding:1.75rem 2rem;flex:1;min-width:220px;">
            <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Deal Readiness Score</div>
            <div style="display:flex;align-items:baseline;gap:12px;">
                <span style="font-size:3rem;font-weight:700;color:{score_color};line-height:1;">{score}</span>
                <span style="font-size:1.2rem;color:#4a4864;">/10</span>
                <span style="background:{badge_bg};color:{score_color};font-size:0.75rem;font-weight:600;padding:4px 12px;border-radius:99px;border:1px solid {score_color}33;">{label}</span>
            </div>
            <div style="font-size:0.8rem;color:#7c7a9a;margin-top:8px;">{reasoning}</div>
        </div>
        <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:12px;padding:1.75rem 2rem;flex:1;min-width:220px;">
            <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Company</div>
            <div style="font-size:1.4rem;font-weight:600;color:#ffffff;">{company_name}</div>
            <div style="font-size:0.8rem;color:#7c7a9a;margin-top:4px;">{domain}</div>
            <div style="display:inline-flex;align-items:center;gap:6px;margin-top:10px;background:#0d0d14;border:1px solid #1e1c2e;border-radius:6px;padding:4px 10px;">
                <span style="width:6px;height:6px;border-radius:50%;background:{dq_color};display:inline-block;"></span>
                <span style="font-size:0.75rem;color:#9d9ab0;">Data quality: {data_quality}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- Company Snapshot ---
    st.markdown(f"""
    <div style="background:#12121e;border:1px solid #1e1c2e;border-left:3px solid #7c3aed;border-radius:0 10px 10px 0;padding:1.25rem 1.5rem;margin-bottom:1.5rem;">
        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">Company Snapshot</div>
        <div style="color:#e2e0f0;font-size:0.9rem;line-height:1.6;">{brief_data.get("company_snapshot", "No snapshot available.")}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- Intelligence Signals (3-4 cards in a grid) ---
    st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Intelligence Signals</div>', unsafe_allow_html=True)
    signals = brief_data.get("key_signals", [])
    sig_cols = st.columns(max(1, min(len(signals), 2)))
    for i, sig in enumerate(signals):
        conf = sig.get("confidence", "low")
        color = "#10b981" if conf == "high" else "#f59e0b" if conf == "medium" else "#ef4444"
        src_badge = {"linkedin":"#1e3a5f","news":"#1a2e1a","website":"#2a1a3e","techstack":"#2d1f00"}.get(sig.get("source",""),"#1a1828")
        src_text = {"linkedin":"#60a5fa","news":"#4ade80","website":"#a78bfa","techstack":"#fbbf24"}.get(sig.get("source",""),"#9d9ab0")
        with sig_cols[i % max(1, min(len(signals), 2))]:
            st.markdown(f"""
            <div style="background:#12121e;border:1px solid #1e1c2e;border-left:3px solid {color};border-radius:0 10px 10px 0;padding:1.25rem;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                    <div style="font-size:0.85rem;font-weight:500;color:#e2e0f0;flex:1;padding-right:8px;">{sig.get("signal")}</div>
                    <span style="background:{src_badge};color:{src_text};font-size:0.65rem;font-weight:600;padding:2px 8px;border-radius:4px;flex-shrink:0;text-transform:uppercase;">{sig.get("source","")}</span>
                </div>
                <div style="font-size:0.8rem;color:#9d9ab0;margin-bottom:10px;">{sig.get("implication")}</div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span style="width:6px;height:6px;border-radius:50%;background:{color};display:inline-block;"></span>
                    <span style="font-size:0.72rem;color:{color};font-weight:500;">{conf.upper()} confidence</span>
                    <span style="font-size:0.72rem;color:#4a4864;"> — {sig.get("confidence_reason","")}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    jobs_data = jobs_data or {}
    if jobs_data.get("job_count", 0) > 0:
        st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 10px;">Live Job Postings (last 60 days)</div>', unsafe_allow_html=True)
        themes = jobs_data.get("hiring_themes", [])
        if themes:
            theme_html = "".join([f'<span style="background:#1a1828;border:1px solid #2a2840;border-radius:4px;padding:2px 8px;font-size:0.72rem;color:#a78bfa;margin-right:6px;">{t}</span>' for t in themes])
            st.markdown(f'<div style="margin-bottom:10px;">{theme_html}</div>', unsafe_allow_html=True)
        job_cols = st.columns(2)
        for i, job in enumerate(jobs_data.get("jobs", [])[:6]):
            with job_cols[i % 2]:
                st.markdown(f'''<div style="background:#12121e;border:1px solid #1e1c2e;border-radius:8px;padding:0.75rem 1rem;margin-bottom:8px;">
                    <div style="font-size:0.82rem;color:#e2e0f0;">{job.get("title")}</div>
                    <div style="font-size:0.7rem;color:#4a4864;margin-top:3px;">{job.get("date","")}</div>
                </div>''', unsafe_allow_html=True)
    
    # --- Talking Points ---
    st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 10px;">Talking Points</div>', unsafe_allow_html=True)
    for i, tp in enumerate(brief_data.get("talking_points", []), 1):
        conf = tp.get("confidence", "low")
        color = "#10b981" if conf == "high" else "#f59e0b" if conf == "medium" else "#7c7a9a"
        st.markdown(f"""
        <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:10px;display:flex;gap:16px;">
            <div style="font-size:1.5rem;font-weight:700;color:#1e1c2e;min-width:28px;">{i:02d}</div>
            <div style="flex:1;">
                <div style="font-size:0.9rem;font-weight:500;color:#e2e0f0;margin-bottom:6px;">{tp.get("point")}</div>
                <div style="font-size:0.78rem;color:#7c7a9a;">{tp.get("why_it_works")}</div>
                <div style="margin-top:8px;display:flex;align-items:center;gap:6px;">
                    <span style="width:5px;height:5px;border-radius:50%;background:{color};display:inline-block;"></span>
                    <span style="font-size:0.7rem;color:{color};">{conf.upper()}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- Bottom row: Email Subjects + Best Persona + Risk Factors ---
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Email Subject Lines</div>', unsafe_allow_html=True)
        approach_colors = {"curiosity":"#7c3aed","pain":"#ef4444","compliment":"#10b981","relevance":"#f59e0b"}
        for email in brief_data.get("email_subject_lines", []):
            approach = email.get("approach", "")
            a_color = approach_colors.get(approach, "#7c7a9a")
            st.markdown(f"""
            <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1rem 1.25rem;margin-bottom:10px;">
                <div style="font-size:0.85rem;font-weight:500;color:#e2e0f0;margin-bottom:6px;">{email.get("subject")}</div>
                <span style="font-size:0.68rem;font-weight:600;color:{a_color};text-transform:uppercase;">{approach}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col_b:
        st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Best Persona to Target</div>', unsafe_allow_html=True)
        persona = brief_data.get("best_persona_to_target", {})
        st.markdown(f"""
        <div style="background:#12121e;border:1px solid #7c3aed33;border-radius:10px;padding:1.25rem;margin-bottom:10px;">
            <div style="width:40px;height:40px;border-radius:50%;background:#2d1f4e;display:flex;align-items:center;justify-content:center;font-size:1.1rem;margin-bottom:10px;">👤</div>
            <div style="font-size:0.95rem;font-weight:600;color:#e2e0f0;margin-bottom:6px;">{persona.get("title","Unknown")}</div>
            <div style="font-size:0.8rem;color:#7c7a9a;line-height:1.5;">{persona.get("why","")}</div>
        </div>
        """, unsafe_allow_html=True)
        
        competitors = brief_data.get("competitor_landscape", [])
        if competitors:
            st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1rem 0 8px;">Competitor Landscape</div>', unsafe_allow_html=True)
            for comp in competitors:
                st.markdown(f'''
                <div style="background:#12121e;border:1px solid #ef444433;border-radius:10px;padding:1rem 1.25rem;margin-bottom:8px;">
                    <div style="font-size:0.9rem;font-weight:600;color:#e2e0f0;margin-bottom:4px;">{comp.get("competitor")}</div>
                    <div style="font-size:0.78rem;color:#7c7a9a;margin-bottom:6px;">{comp.get("evidence")}</div>
                    <div style="font-size:0.78rem;color:#10b981;">Our edge: {comp.get("our_edge")}</div>
                </div>''', unsafe_allow_html=True)
    
    with col_c:
        st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">Risk Factors</div>', unsafe_allow_html=True)
        for risk in brief_data.get("risk_factors", []):
            st.markdown(f"""
            <div style="background:#1a0a0a;border:1px solid #ef444433;border-left:3px solid #ef4444;border-radius:0 8px 8px 0;padding:0.75rem 1rem;margin-bottom:8px;font-size:0.82rem;color:#fca5a5;">
                {risk}
            </div>
            """, unsafe_allow_html=True)
        
    st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 10px;">Objection Handler</div>', unsafe_allow_html=True)
    trigger_colors = {"techstack":"#fbbf24","news":"#4ade80","website":"#a78bfa","linkedin":"#60a5fa"}
    for obj in brief_data.get("objection_handler", []):
        t_color = trigger_colors.get(obj.get("trigger",""),"#9d9ab0")
        st.markdown(f'''
        <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1.25rem;margin-bottom:10px;">
            <div style="font-size:0.8rem;color:#ef4444;font-weight:500;margin-bottom:6px;">"{obj.get("objection")}"</div>
            <div style="font-size:0.85rem;color:#e2e0f0;margin-bottom:8px;">↳ {obj.get("rebuttal")}</div>
            <span style="font-size:0.68rem;color:{t_color};text-transform:uppercase;font-weight:600;">signal from {obj.get("trigger","")}</span>
        </div>''', unsafe_allow_html=True)
        

# --- MAIN AREA ---
st.markdown("""
<div style="margin-bottom: 1.5rem;">
    <div style="font-size: 0.75rem; color: #7c7a9a; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px;">Sales Intelligence</div>
    <h1 style="font-size: 1.8rem; font-weight: 700; color: #ffffff; margin: 0; letter-spacing: -0.02em;">Generate Pre-Call Brief</h1>
    <p style="color: #7c7a9a; margin: 4px 0 0; font-size: 0.9rem;">Enter a company domain and your product to get a full AI-powered sales brief in seconds.</p>
</div>
""", unsafe_allow_html=True)


mode = st.radio("Mode", ["Single domain", "Batch (multiple domains)"], horizontal=True, label_visibility="collapsed")

if mode == "Batch (multiple domains)":
    batch_input = st.text_area("Enter domains (one per line, max 5)", placeholder="stripe.com\nnotion.so\nvercel.com", height=120)
    batch_product = st.text_area("Your Product (same for all)", placeholder="e.g. AI fraud detection for fintech", height=68)
    batch_btn = st.button("Run Batch Research", use_container_width=True)
    
    if batch_btn:
        domains_list = [d.strip() for d in batch_input.strip().split("\n") if d.strip()][:5]
        if not domains_list or not batch_product:
            st.error("Enter at least one domain and your product.")
        else:
            batch_results = {}
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, d in enumerate(domains_list):
                status_text.markdown(f'<div style="font-size:0.85rem;color:#9d9ab0;">Researching {d} ({i+1}/{len(domains_list)})...</div>', unsafe_allow_html=True)
                try:
                    result = run_pipeline(d, batch_product)
                    batch_results[d] = result
                except Exception as e:
                    batch_results[d] = {"error": str(e)}
                progress_bar.progress((i+1)/len(domains_list))
            
            status_text.markdown('<div style="font-size:0.85rem;color:#10b981;">Batch complete!</div>', unsafe_allow_html=True)
            
            # Show summary table
            st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 8px;">Batch Results</div>', unsafe_allow_html=True)
            for d, res in batch_results.items():
                if "error" in res and "brief_data" not in res:
                    score, label, snap = "ERR", "Error", str(res["error"])[:80]
                else:
                    bd = res.get("brief_data",{})
                    score = bd.get("deal_readiness_score",{}).get("score","?")
                    label = bd.get("deal_readiness_score",{}).get("label","?")
                    snap = bd.get("company_snapshot","")[:120]
                score_color = "#10b981" if label=="Hot" else "#f59e0b" if label=="Warm" else "#7c7a9a"
                st.markdown(f'''
                <div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1rem 1.25rem;margin-bottom:8px;display:flex;gap:16px;align-items:flex-start;">
                    <div style="min-width:80px;">
                        <div style="font-size:0.75rem;color:#7c7a9a;">{d}</div>
                        <div style="font-size:1.4rem;font-weight:700;color:{score_color};">{score}/10</div>
                        <div style="font-size:0.7rem;color:{score_color};">{label}</div>
                    </div>
                    <div style="font-size:0.8rem;color:#9d9ab0;line-height:1.5;padding-top:4px;">{snap}...</div>
                </div>''', unsafe_allow_html=True)

else:
    col1, col2 = st.columns(2)
    with col1:
        domain = st.text_input("🌐 Company Domain", value=st.session_state.domain_input, placeholder="e.g. stripe.com")
    with col2:
        product = st.text_area("📦 Your Product", placeholder="e.g. AI fraud detection for fintech", height=68)
    
    
    if st.session_state.get("viewing_historical"):
        hist_brief = st.session_state["viewing_historical"]
        hist_date = st.session_state.get("viewing_historical_date","")
        st.markdown(f'''<div style="background:#1a1200;border:1px solid #f59e0b44;border-left:3px solid #f59e0b;border-radius:0 8px 8px 0;padding:0.6rem 1rem;margin-bottom:1rem;font-size:0.8rem;color:#fbbf24;">
        Viewing historical brief from {hist_date[:10]}. <a href="#" onclick="window.location.reload()" style="color:#f59e0b;">Clear</a></div>''', unsafe_allow_html=True)
        render_brief_tab(hist_brief, st.session_state.get("domain_input", "unknown"), st.session_state.get("viewing_historical_jobs", {}))
        if st.button("← Back to current", key="back_current"):
            del st.session_state["viewing_historical"]
            st.rerun()
    
    generate_btn = st.button("Generate Brief", use_container_width=True)
    
    if generate_btn:
        if not domain or not product:
            st.error("Please enter both a company domain and a product description.")
        else:
            st.session_state.domain_input = domain
            
            try:
                with st.status("Generating DealRadar Brief...", expanded=True) as status:
                    result = run_pipeline(domain, product, status_callback=status.write)
                    status.update(label="Brief generated successfully!", state="complete", expanded=False)
                    
                brief_data = result["brief_data"]
                pdf_path = result["pdf_path"]
                diff_data = result["diff_data"]
                is_returning = result["is_returning_company"]
                
                missing = brief_data.get("data_quality", {}).get("missing_data_warnings", [])
                if missing:
                    st.markdown(f'''<div style="background:#1c1a00;border:1px solid #854f0b44;border-left:3px solid #f59e0b;border-radius:8px;padding:0.6rem 1rem;margin-bottom:1rem;font-size:0.78rem;color:#d4a017;line-height:1.5;">
      <strong style="color:#f59e0b;">Data gaps:</strong> {" · ".join(missing)}</div>''', unsafe_allow_html=True)
                
                if "error" in brief_data:
                    st.error("Failed to generate brief due to an error during synthesis.")
                    st.write(brief_data["error"])
                else:
                    tabs_list = ["📊 Brief", "📄 PDF Report"]
                    if is_returning:
                        tabs_list.append("🔄 Memory & Changes")
                        
                    tabs = st.tabs(tabs_list)
                    
                    # --- TAB 1: BRIEF ---
                    with tabs[0]:
                        # --- Row 1: Deal Score card + Data Quality warnings ---
                        render_brief_tab(brief_data, domain, result.get("jobs_data", {}))
                    # --- TAB 2: PDF REPORT ---
                    with tabs[1]:
                        renderer = PDFRenderer()
                        html_content = renderer.render_html(brief_data, domain)
    
                        if pdf_path and os.path.exists(pdf_path) and pdf_path.endswith(".pdf"):
                            col_dl1, col_dl2 = st.columns([1,3])
                            with col_dl1:
                                with open(pdf_path, "rb") as f:
                                    st.download_button(
                                        label="Download PDF",
                                        data=f,
                                        file_name=os.path.basename(pdf_path),
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                        elif pdf_path and os.path.exists(pdf_path) and pdf_path.endswith(".html"):
                            col_dl1, col_dl2 = st.columns([1,3])
                            with col_dl1:
                                with open(pdf_path, "rb") as f:
                                    st.download_button(
                                        label="Download HTML Report",
                                        data=f,
                                        file_name=os.path.basename(pdf_path),
                                        mime="text/html",
                                        use_container_width=True
                                    )
                            with col_dl2:
                                st.markdown("""<div style="font-size:0.8rem;color:#7c7a9a;padding:0.6rem 0;">PDF export requires GTK+ libraries. HTML report is identical in content.</div>""", unsafe_allow_html=True)
                        else:
                            st.markdown("""<div style="background:#12121e;border:1px solid #ef444433;border-radius:10px;padding:1.5rem;color:#fca5a5;font-size:0.85rem;">Report file not found. The brief data is available in the Brief tab.</div>""", unsafe_allow_html=True)
    
                        st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 8px;">Report Preview</div>', unsafe_allow_html=True)
                        components.html(html_content, height=800, scrolling=True)
                            
                    # --- TAB 3: MEMORY & CHANGES ---
                    if is_returning and len(tabs) > 2:
                        with tabs[2]:
                            if diff_data:
                                deal_change = diff_data.get("deal_score_change", {})
                                prev_score = deal_change.get("previous", 0)
                                curr_score = deal_change.get("current", 0)
                                delta = deal_change.get("delta", 0)
                                direction = deal_change.get("direction", "unchanged")
                                delta_color = "#10b981" if delta > 0 else "#ef4444" if delta < 0 else "#7c7a9a"
                                arrow = "▲" if delta > 0 else "▼" if delta < 0 else "—"
                            
                                m1, m2, m3 = st.columns(3)
                                with m1:
                                    st.markdown(f"""<div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1.25rem 1.5rem;">
                                        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Previous Score</div>
                                        <div style="font-size:2rem;font-weight:700;color:#7c7a9a;">{prev_score}/10</div>
                                    </div>""", unsafe_allow_html=True)
                                with m2:
                                    st.markdown(f"""<div style="background:#12121e;border:1px solid #1e1c2e;border-radius:10px;padding:1.25rem 1.5rem;">
                                        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Current Score</div>
                                        <div style="font-size:2rem;font-weight:700;color:#ffffff;">{curr_score}/10</div>
                                    </div>""", unsafe_allow_html=True)
                                with m3:
                                    st.markdown(f"""<div style="background:#12121e;border:1px solid {delta_color}33;border-radius:10px;padding:1.25rem 1.5rem;">
                                        <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">Change</div>
                                        <div style="font-size:2rem;font-weight:700;color:{delta_color};">{arrow} {abs(delta)}</div>
                                    </div>""", unsafe_allow_html=True)
                            
                                st.markdown(f"""<div style="background:#12121e;border:1px solid #1e1c2e;border-left:3px solid #7c3aed;border-radius:0 10px 10px 0;padding:1.25rem 1.5rem;margin:1.5rem 0;">
                                    <div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">Summary</div>
                                    <div style="color:#e2e0f0;font-size:0.9rem;">{diff_data.get("summary","No significant changes detected.")}</div>
                                </div>""", unsafe_allow_html=True)
                            
                                col_c, col_d = st.columns(2)
                                with col_c:
                                    st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">New Signals</div>', unsafe_allow_html=True)
                                    new_sigs = diff_data.get("new_signals", [])
                                    if new_sigs:
                                        for sig in new_sigs:
                                            st.markdown(f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #1e1c2e;font-size:0.85rem;color:#e2e0f0;"><span style="width:8px;height:8px;border-radius:50%;background:#10b981;flex-shrink:0;"></span>{sig["signal"]} <span style="color:#4a4864;font-size:0.75rem;">({sig["source"]})</span></div>', unsafe_allow_html=True)
                                    else:
                                        st.markdown('<div style="color:#4a4864;font-size:0.85rem;">No new signals</div>', unsafe_allow_html=True)
                                with col_d:
                                    st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Dropped Signals</div>', unsafe_allow_html=True)
                                    dropped = diff_data.get("dropped_signals", [])
                                    if dropped:
                                        for sig in dropped:
                                            st.markdown(f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #1e1c2e;font-size:0.85rem;color:#e2e0f0;"><span style="width:8px;height:8px;border-radius:50%;background:#ef4444;flex-shrink:0;"></span>{sig["signal"]} <span style="color:#4a4864;font-size:0.75rem;">({sig["source"]})</span></div>', unsafe_allow_html=True)
                                    else:
                                        st.markdown('<div style="color:#4a4864;font-size:0.85rem;">No dropped signals</div>', unsafe_allow_html=True)
                            
                                st.markdown('<div style="font-size:0.7rem;color:#7c7a9a;text-transform:uppercase;letter-spacing:0.08em;margin:1.5rem 0 8px;">Research Timeline</div>', unsafe_allow_html=True)
                                timeline = memory.get_research_timeline(domain)
                                import pandas as pd
                                df = pd.DataFrame(timeline)
                                if not df.empty:
                                    df.columns = ["ID", "Researched At", "Deal Score", "Label"]
                                st.dataframe(df, use_container_width=True, hide_index=True)
                                
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")
                st.warning("Please verify your API keys and check the terminal logs for details.")
