# 🎯 DealRadar: AI-Powered Sales Intelligence Agent

DealRadar is a self-contained AI-powered sales intelligence system that aggregates real-time signals from multiple sources and synthesizes a comprehensive Pre-Call Brief for sales representatives. Before entering a high-stakes call or sending a cold email, an Account Executive (AE) can query DealRadar to discover key pain points, technology stack gaps, hiring themes, and recent news, combined with actionable talking points and personalized email subjects.

---

## 🏗️ Architecture Summary

DealRadar is designed with a decentralized, multi-agent parallel data-gathering architecture overseen by a central pipeline runner, backed by a persistent SQLite database for historical intelligence tracking.

```mermaid
graph TD
    A[Streamlit Web UI / CLI] -->|Trigger Research| B[Pipeline Coordinator (main.py)]
    B -->|Parallel Execution via Threads| C1[Web Scraper Agent]
    B -->|Parallel Execution via Threads| C2[News Agent]
    B -->|Parallel Execution via Threads| C3[Tech Stack Agent]
    B -->|Parallel Execution via Threads| C4[LinkedIn Agent]
    B -->|Parallel Execution via Threads| C5[Jobs Agent]
    
    C1 -->|Fetch Page Details| D1[HTML Homepage / About / Blog]
    C2 -->|Fetch Press & Mentions| D2[NewsAPI / Google News RSS]
    C3 -->|Detect Tech Stack| D3[BuiltWith API / HTML Signature Scan]
    C4 -->|Fetch Headcount & Roles| D4[LinkdAPI]
    C5 -->|Fetch Postings| D5[Indeed RSS]
    
    D1 & D2 & D3 & D4 & D5 -->|Aggregated Context| E[Claude Synthesis Engine (Synthesizer)]
    E -->|Structured Prompting| F[Anthropic Claude API]
    F -->|Raw JSON Output| E
    
    E -->|Formatted JSON Brief| B
    B -->|Save History & Calculate Changes| G[(SQLite Memory Store)]
    B -->|Compile PDF/HTML Brief| H[PDF/HTML Renderer]
    
    G -.->|Query Historical Briefs| A
```

### Core Architecture Components

1. **Pipeline Coordinator (`main.py`)**: Spawns multiple threads to orchestrate simultaneous data collection from the 5 specialized agents.
2. **Parallel Intelligence Agents**:
   - **WebScraper Agent**: Fetches the company homepage, `/about`, and `/blog` to extract core value propositions and direct funding mentions.
   - **News Agent**: Uses NewsAPI to find recent media mentions, falling back gracefully to Google News RSS if no API key is provided or the service is down.
   - **Tech Stack Agent**: Calls the BuiltWith API to detect CRM, Marketing Automation, Support, and Analytics tools, falling back to a signature-based scan of the landing page.
   - **LinkedIn Agent**: Queries LinkdAPI to extract headcount brackets, headquarters, and open job roles, returning an empty state gracefully if credentials are not configured.
   - **Jobs Agent**: Scrapes Indeed RSS and applies keyword matching to derive high-level hiring themes (e.g., engineering growth, sales expansion).
3. **Synthesis Engine (`agents/synthesizer.py`)**: Constructs a detailed context payload from all active agents and uses Anthropic's Claude to generate a structured, highly personalized sales brief.
4. **SQLite Memory Store (`memory/store.py`)**: Saves each run to a local database (`cache/dealradar_memory.db`). If a domain is re-analyzed later, it automatically calculates the score delta, new signals, and dropped signals.
5. **Output Renderer (`output/renderer.py`)**: Uses Jinja2 templates to generate responsive HTML preview widgets and utilizes WeasyPrint to compile premium PDF reports.

---

## 🌟 Key Features

* **Parallel Intelligence Gathering**: Collects information across 5 data vectors simultaneously in under 30 seconds using python multithreading.
* **Intelligent Score Delta & Timeline**: Tracks previous research for returning domains and displays a dynamic delta (e.g., Score changed +2, New/Dropped signals timeline).
* **Graceful API Fallbacks**: Designed to run successfully even with zero API keys by falling back to web scraping, RSS parsing, and heuristic-based analyses.
* **Premium PDF & HTML Briefs**: Renders a visually clean Pre-Call Brief containing categorized talking points, risk factors, target personas, and objection handlers.
* **Batch Mode Execution**: Supports researching up to 5 domains sequentially inside the Web UI for high-velocity preparation.
* **Robust CLI Support**: Fully integrated CLI script for terminal automation or batch scripts.

---

## 🛠️ Tech Stack

* **Front-End & Application Framework**: Streamlit (Premium dark glassmorphism theme)
* **LLM Engine**: Anthropic Claude API (via `anthropic` client SDK)
* **Data Retrieval & Parsing**: `requests`, `beautifulsoup4`, `lxml`
* **Local Database**: SQLite3 (Standard Python Library)
* **Formatting & Terminal Styling**: Jinja2, `rich`
* **PDF Compilation**: WeasyPrint (with graceful raw HTML fallback if system-level GTK+ libraries are missing)

---

## 🚀 Local Setup & Installation

### Prerequisites
* Python 3.10 or higher
* (Optional for PDF generation) [WeasyPrint system dependencies](https://doc.weasyprint.org/stable/first_steps.html) (GTK+ runtime libraries). If skipped, DealRadar will gracefully output identical HTML documents instead of PDFs.

### 1. Clone & Install Dependencies
```bash
# Clone the repository
git clone https://github.com/tuvya-algotar/dealradar.git
cd dealradar

# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and enter your API keys. 

```bash
cp .env.example .env
```

Open `.env` and fill in the values:
```env
# Required for AI Synthesis
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: LLM Configuration overrides
LLM_MODEL=claude-haiku-4-5-20251001
LLM_BASE_URL=

# Optional: Add keys to enable premium data sources
NEWS_API_KEY=your_newsapi_key_here
BUILTWITH_API_KEY=your_builtwith_api_key_here
LINKDAPI_API_KEY=your_linkdapi_key_here
```

---

## 💻 How to Run

### Run the Web Interface (Recommended)
Launch the Streamlit web application:
```bash
streamlit run app.py
```
This will open the DealRadar application in your browser (typically at `http://localhost:8501`).

### Run via Command Line Interface (CLI)
You can run the pipeline directly from your terminal:
```bash
python main.py --domain notion.so --product "AI workflow automation platform for operations teams"
```
The resulting JSON brief and PDF/HTML report will be generated and saved inside the `reports/` folder.

### Run Agent Verification Tests
Validate your environment variables and agent integration:
```bash
python test_agents.py
```

---

## 🖼️ Application Screenshots

*Screenshots demonstrating the visual interface are shown below (Placeholder section).*

| Dashboard & Score Delta | Pre-Call Brief Preview |
| :--- | :--- |
| ![Dashboard Mockup](https://raw.githubusercontent.com/tuvya-algotar/dealradar/main/reports/.gitkeep) *Interactive Score timeline* | ![Brief Mockup](https://raw.githubusercontent.com/tuvya-algotar/dealradar/main/reports/.gitkeep) *Structured Talking Points* |

---

## ⚠️ Limitations & Reality Check

* **Scraping Dependability**: Fallback website scanning and RSS parsing rely on public page structures. Highly secure sites behind Cloudflare challenge walls might occasionally result in reduced website content depth.
* **LinkedIn Scraping**: Standard search matches slugs strictly. If a company's legal name differs significantly from its domain prefix, the LinkedIn agent may report an empty/unknown state.
* **Rate Limits**: Free/Trial versions of NewsAPI and BuiltWith have strict monthly credit limits. Utilize the fallbacks when executing massive batches.

---

## 📈 Future Improvements

* **OAuth CRM Integrations**: Automatically pushing generated briefs directly into Salesforce or HubSpot contact records.
* **Enhanced Cloudflare Bypass**: Incorporating headless browsers or scraping API proxies to improve scraping coverage for highly protected enterprise sites.
* **Browser Extension**: A lightweight Chrome extension to generate pre-call briefs on the fly when browsing LinkedIn or company profiles.
