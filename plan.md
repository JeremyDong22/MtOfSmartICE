# MtOfSmartICE - Meituan Shangjia Stats Crawler

## Project Overview

**Purpose:** Automated browser crawler for Meituan Shangjia (商家后台) - the merchant statistics dashboard that Meituan provides for restaurant owners and business operators. Manually downloading stats is tedious and time-consuming; this tool automates the entire process.

**Target Platform:** Meituan Shangjia (美团商家后台)
**Tech Stack:** Playwright + Python (FastAPI backend)
**Reference Implementation:** `../XHSCOfSmartICE` (Xiaohongshu crawler)

---

## Core Architecture (Inherited from XHS Project)

### Session Persistence Technique

```python
# The key mechanism - Playwright persistent context
context = await playwright.chromium.launch_persistent_context(
    user_data_path="user_data/session_1/",  # Stores all cookies, localStorage, session data
    headless=False,
    channel='chrome',
    args=['--disable-blink-features=AutomationControlled']  # Anti-detection
)
```

**Why this works:**
- Chrome profile stored at `user_data/session_X/` contains all authentication data
- Cookies, localStorage, IndexedDB, ServiceWorker cache all preserved
- Next launch = same logged-in session, no re-authentication needed
- Survives application restarts and crashes

---

## Development Phases & Multi-Agent Workflow

### Phase 1: Foundation Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT SWARM: PHASE 1                         │
│                   (Parallel Execution)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐     ┌─────────────────────┐          │
│   │   AGENT 1A          │     │   AGENT 1B          │          │
│   │   Backend Scaffold  │     │   MCP Integration   │          │
│   │                     │     │                     │          │
│   │ • Create backend/   │     │ • Configure Chrome  │          │
│   │ • FastAPI app.py    │     │   DevTools MCP      │          │
│   │ • browser_manager   │     │ • Setup .mcp.json   │          │
│   │ • session_manager   │     │ • Test MCP connect  │          │
│   │ • requirements.txt  │     │   to live browser   │          │
│   └──────────┬──────────┘     └──────────┬──────────┘          │
│              │                           │                      │
│              └───────────┬───────────────┘                      │
│                          ▼                                      │
│              ┌─────────────────────┐                            │
│              │   AGENT 1C          │                            │
│              │   Integration Test  │                            │
│              │                     │                            │
│              │ • Verify browser    │                            │
│              │   opens correctly   │                            │
│              │ • Test persistent   │                            │
│              │   context works     │                            │
│              │ • Confirm MCP can   │                            │
│              │   inspect elements  │                            │
│              └─────────────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent 1A Tasks - Backend Scaffold
- [ ] Create `backend/` directory structure
- [ ] Create `backend/browser_manager.py` - Playwright persistent context manager
- [ ] Create `backend/session_manager.py` - Account/session tracking
- [ ] Create `backend/api.py` - FastAPI REST endpoints
- [ ] Create `requirements.txt` with dependencies:
  - playwright
  - fastapi
  - uvicorn
  - pydantic

#### Agent 1B Tasks - MCP Integration
- [ ] Add Chrome DevTools MCP to project-level `.mcp.json`
- [ ] Configure MCP server connection parameters
- [ ] Document MCP usage for element inspection
- [ ] Test connection between Claude and live browser

---

### Phase 2: Manual Login & Session Capture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HUMAN + AGENT COLLABORATION                  │
│                   (Sequential - Human Required)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐                                       │
│   │   AGENT 2A          │                                       │
│   │   Browser Launcher  │                                       │
│   │                     │                                       │
│   │ • Launch Playwright │                                       │
│   │   browser with      │                                       │
│   │   persistent ctx    │                                       │
│   │ • Navigate to       │                                       │
│   │   Meituan login     │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                  │
│              ▼                                                  │
│   ┌─────────────────────┐                                       │
│   │   HUMAN ACTION      │                                       │
│   │   Manual Login      │                                       │
│   │                     │                                       │
│   │ • User scans QR or  │                                       │
│   │   enters credentials│                                       │
│   │ • Navigate to stats │                                       │
│   │   pages manually    │                                       │
│   │ • Signal completion │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                  │
│              ▼                                                  │
│   ┌─────────────────────┐                                       │
│   │   AGENT 2B          │                                       │
│   │   Session Validator │                                       │
│   │                     │                                       │
│   │ • Verify login OK   │                                       │
│   │ • Check session     │                                       │
│   │   persisted to disk │                                       │
│   │ • Test re-open      │                                       │
│   │   maintains login   │                                       │
│   └─────────────────────┘                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent 2A Tasks - Browser Launcher
- [ ] Create launch script `backend/launch_browser.py`
- [ ] Configure `user_data/meituan_session/` as persistent storage
- [ ] Navigate to Meituan Shangjia login page
- [ ] Wait for human to complete login

#### Human Tasks
- [ ] Scan QR code or enter credentials
- [ ] Navigate through the dashboard
- [ ] Identify key stats pages to scrape
- [ ] Signal completion to Agent 2B

#### Agent 2B Tasks - Session Validator
- [ ] Verify session cookies saved to `user_data/`
- [ ] Close and reopen browser to confirm persistence
- [ ] Document successful session capture

---

### Phase 3: Page Analysis & Scraping Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT SWARM: PHASE 3                         │
│              (Parallel - DevTools MCP Powered)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐     ┌─────────────────────┐          │
│   │   AGENT 3A          │     │   AGENT 3B          │          │
│   │   DOM Inspector     │     │   API Analyzer      │          │
│   │                     │     │                     │          │
│   │ • Use Chrome        │     │ • Use Network tab   │          │
│   │   DevTools MCP      │     │   via MCP           │          │
│   │ • Identify stats    │     │ • Capture XHR/Fetch │          │
│   │   table selectors   │     │   requests          │          │
│   │ • Map download      │     │ • Document API      │          │
│   │   button paths      │     │   endpoints         │          │
│   │ • Extract JS paths  │     │ • Identify auth     │          │
│   │   for data access   │     │   headers needed    │          │
│   └──────────┬──────────┘     └──────────┬──────────┘          │
│              │                           │                      │
│              └───────────┬───────────────┘                      │
│                          ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┤
│   │                    AGENT 3C                                 │
│   │              Scraper Implementation                         │
│   │                                                             │
│   │ • Create backend/meituan_scraper.py                        │
│   │ • Implement navigation to stats pages                       │
│   │ • Write JS evaluation scripts for data extraction           │
│   │ • Handle pagination/date range selection                    │
│   │ • Implement download automation                             │
│   └─────────────────────────────────────────────────────────────┘
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent 3A Tasks - DOM Inspector (via MCP)
- [ ] Connect to live browser via Chrome DevTools MCP
- [ ] Inspect Shangjia stats page DOM structure
- [ ] Document CSS selectors for:
  - Stats tables
  - Date range pickers
  - Download buttons
  - Export format options
- [ ] Identify JavaScript objects holding data

#### Agent 3B Tasks - API Analyzer (via MCP)
- [ ] Monitor Network tab for XHR/Fetch requests
- [ ] Capture API endpoints used by the dashboard
- [ ] Document request/response formats
- [ ] Identify authentication headers (cookies, tokens)
- [ ] Determine if direct API calls are more efficient

#### Agent 3C Tasks - Scraper Implementation
- [ ] Create `backend/meituan_scraper.py`
- [ ] Implement `MeituanScraper` class
- [ ] Methods to implement:
  - `navigate_to_stats()`
  - `select_date_range(start, end)`
  - `extract_stats_data()`
  - `trigger_download()`
  - `wait_for_download()`
- [ ] Handle all edge cases and errors

---

### Phase 4: Export & Storage

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT SWARM: PHASE 4                         │
│                   (Parallel Execution)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐     ┌─────────────────────┐          │
│   │   AGENT 4A          │     │   AGENT 4B          │          │
│   │   Download Handler  │     │   Data Processor    │          │
│   │                     │     │                     │          │
│   │ • Configure         │     │ • Parse downloaded  │          │
│   │   download path     │     │   Excel/CSV files   │          │
│   │ • Handle download   │     │ • Normalize data    │          │
│   │   events            │     │   structure         │          │
│   │ • Move files to     │     │ • Store in unified  │          │
│   │   output/           │     │   format            │          │
│   └──────────┬──────────┘     └──────────┬──────────┘          │
│              │                           │                      │
│              └───────────┬───────────────┘                      │
│                          ▼                                      │
│              ┌─────────────────────┐                            │
│              │   AGENT 4C          │                            │
│              │   Scheduler         │                            │
│              │                     │                            │
│              │ • Create cron/      │                            │
│              │   scheduled task    │                            │
│              │ • Auto-run daily/   │                            │
│              │   weekly scrapes    │                            │
│              │ • Handle failures   │                            │
│              │   and retries       │                            │
│              └─────────────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent 4A Tasks - Download Handler
- [ ] Configure Playwright download path
- [ ] Implement download event listeners
- [ ] Handle file naming conventions
- [ ] Create `output/` directory structure:
  ```
  output/
  ├── raw/           # Original downloaded files
  ├── processed/     # Normalized data
  └── logs/          # Scrape logs
  ```

#### Agent 4B Tasks - Data Processor
- [ ] Parse Excel (`.xlsx`) files using openpyxl/pandas
- [ ] Parse CSV files
- [ ] Normalize data structure across different report types
- [ ] Create unified JSON/database storage

#### Agent 4C Tasks - Scheduler
- [ ] Create scheduling mechanism
- [ ] Configure auto-run intervals (daily/weekly)
- [ ] Implement retry logic for failures
- [ ] Add notification on completion/failure

---

### Phase 5: Frontend Dashboard (Optional)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT SWARM: PHASE 5                         │
│                   (Parallel - Optional)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────┐     ┌─────────────────────┐          │
│   │   AGENT 5A          │     │   AGENT 5B          │          │
│   │   Next.js Setup     │     │   API Endpoints     │          │
│   │                     │     │                     │          │
│   │ • Create frontend/  │     │ • Add REST APIs:    │          │
│   │ • Setup Next.js 15  │     │   - GET /stats      │          │
│   │ • Configure Tailwind│     │   - POST /scrape    │          │
│   │ • Create layout     │     │   - GET /status     │          │
│   └──────────┬──────────┘     └──────────┬──────────┘          │
│              │                           │                      │
│              └───────────┬───────────────┘                      │
│                          ▼                                      │
│              ┌─────────────────────┐                            │
│              │   AGENT 5C          │                            │
│              │   UI Components     │                            │
│              │                     │                            │
│              │ • Stats dashboard   │                            │
│              │ • Scrape controls   │                            │
│              │ • Progress logs     │                            │
│              │ • Data visualization│                            │
│              └─────────────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure (Planned)

```
MtOfSmartICE/
├── plan.md                          # This file
├── .mcp.json                        # Chrome DevTools MCP config
├── requirements.txt                 # Python dependencies
│
├── backend/
│   ├── api.py                       # FastAPI main app
│   ├── browser_manager.py           # Playwright context manager
│   ├── session_manager.py           # Session persistence
│   ├── meituan_scraper.py          # Scraping logic
│   ├── download_handler.py          # File download management
│   ├── data_processor.py            # Data normalization
│   └── scheduler.py                 # Auto-run scheduling
│
├── user_data/
│   └── meituan_session/             # Persistent Chrome profile
│       └── Default/                 # Cookies, localStorage, etc.
│
├── output/
│   ├── raw/                         # Original downloaded files
│   ├── processed/                   # Normalized JSON data
│   └── logs/                        # Scrape operation logs
│
└── frontend/ (optional)
    ├── src/
    │   ├── app/
    │   └── components/
    └── package.json
```

---

## Key Technical Decisions

### 1. Browser-Based vs API-Direct Scraping

**Chosen: Browser-Based (like XHS project)**

Reasons:
- Meituan uses complex authentication (likely multi-factor)
- Session cookies are easier to capture via browser
- Can visually verify scraping is working
- Handles JavaScript-rendered content
- Download files directly as Meituan exports them

### 2. Headful vs Headless Browser

**Chosen: Headful (visible browser)**

Reasons:
- Easier to debug during development
- User can monitor scraping progress
- Less likely to trigger anti-bot detection
- Required for initial manual login

### 3. Session Persistence Strategy

**Chosen: Playwright `launch_persistent_context()`**

Same as XHS project:
```python
context = await playwright.chromium.launch_persistent_context(
    "user_data/meituan_session/",
    headless=False,
    channel='chrome',
    args=['--disable-blink-features=AutomationControlled']
)
```

---

## Next Steps (Immediate)

1. **Configure Chrome DevTools MCP** at project level
2. **Launch browser** with persistent context
3. **Human login** to Meituan Shangjia
4. **Analyze page structure** using MCP DevTools
5. **Design scraping selectors** based on actual DOM

---

## Notes

- Reference XHS implementation: `../XHSCOfSmartICE/backend/`
- Key files to study:
  - `browser_manager.py` - persistent context pattern
  - `xiaohongshu_scraper.py` - scraping patterns
  - `api.py` - REST endpoint patterns
