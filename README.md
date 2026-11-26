# BreatheWise AI — Urban Air Quality & Personalized Exposure Assistant

**PromptWars Virtual Challenge 6 (Hack2Skill)** | *Your personal air quality and lifestyle assistant for Indian metropolitan cities.*

- **Live Web App (Vercel):** https://breathewiseai-frontend.vercel.app
- **Live Backend API (Render):** https://breathewise-ai-peea.onrender.com
- **Demo Video:** *[Demo Video Link — Unlisted YouTube / Google Drive link to be added prior to final submission]* (see [Demo Script](docs/DEMO_SCRIPT_AND_SUBMISSION.md))

---

## 1. Project Purpose & Selected Challenge Vertical

- **Selected Vertical:** **Urban Air Quality Assistant**
- **Problem Statement:** Urban residents across Indian metropolitan regions face sharp hourly and neighborhood-level swings in $PM_{2.5}$, $PM_{10}$, $O_3$, $NO_2$, $SO_2$, $CO$, $NH_3$, and $Pb$. Standard AQI apps only report a static city-wide number—leaving families without practical guidance on *when* to schedule outdoor tasks, *how* to manage indoor cooking (*tadka*) vs. window ventilation, or *which* lower-exposure commute options fit their household.
- **Solution:** BreatheWise AI connects multi-tier environmental telemetry and hourly atmospheric chemistry forecasts with deterministic CPCB/MoHFW public-health rules and personalized AI routine planning.

---

## 2. Target Personas

- **Parent / Household with Children:** Evaluates school commutes, outdoor play restrictions, and indoor dust/cooking smoke mitigation.
- **Senior Citizen / Vulnerable Member:** Adapts exertion thresholds and cardiovascular/respiratory precautions conservatively without issuing medical prescriptions.
- **Athlete / Runner:** Times outdoor workouts around comparative diurnal exposure windows and automatically shifts cardio indoors during Very Poor / Severe bands.
- **Daily Urban Commuter:** Contrasts open two-wheeler / auto-rickshaw exposure against enclosed Metro / AC transit and contextualizes N95/FFP2 usage.
- **General Resident:** Provides clear pollutant breakdowns, data provenance, and actionable daily routines.

---

## 3. Key Features

1. **Pan-India City Discovery (28 States & 8 Union Territories):** Centralized geographic catalog (`backend/app/data/india_cities.json`) covering **48 Indian cities across all 28 States and 8 Union Territories**, with alias matching (e.g., *Trivandrum → Thiruvananthapuram*, *Gurgaon → Gurugram*, *Pondicherry → Puducherry*) and State/UT filtering. Live ground station coverage depends on real provider availability rather than being assumed across all catalog cities.
2. **3-Tier Data Provenance Pipeline & Measurement Types:**
   - **Tier 1 (Ground Stations):** WAQI primary, OpenAQ v3 secondary.
   - **Tier 2 (Atmospheric Model):** Open-Meteo CAMS fallback (strictly labeled `atmospheric_model_estimate`).
   - **Tier 3 (Unavailable State):** Explicit unavailable UI when live data cannot be verified (never fabricates measurements).
   - **Five Measurement Types:** Explicitly distinguishes **Raw Concentration (`µg/m³`/`mg/m³`)**, **WAQI Provider Index (`US-EPA AQI`)**, **CPCB Sub-Index**, **Model Estimate (CAMS)**, and **Unavailable**—plus PRD v1.2 timezone-aware **Live (≤3h) / Stale (3–12h) / Expired (>12h triggering model fallback)** freshness tracking.
3. **Interactive Pollutant Map:** Leaflet + OpenStreetMap visualization displaying real monitoring station coordinates, measurement-aware summary cards, station-level provider indices or model concentrations, freshness labels, and unavailable explanations.
4. **Best Air Window Engine:** Evaluates 24–48h Open-Meteo CAMS hourly forecasts via $E(t) = \max(I_p(t))$ and renders an interactive Recharts trend chart labeled strictly as `"Lowest Forecast Pollution Period"`, `"Comparatively Better Window"`, or `"Higher Pollution Period"`.
5. **Personalized Daily Planner (Location-Decoupled Dual-AI + Fallback):** Selecting any city updates telemetry and forecast context while preserving the user's chosen household persona, commute mode, and sensitivities. Synthesizes Morning, Afternoon, and Evening routines via **Groq Llama 3** -> **Google Gemini** -> **Pure-Python Deterministic Generator**.

---

## 4. System Architecture

```mermaid
flowchart TD
    UI[Next.js 16 + TypeScript + Tailwind + Recharts + Leaflet] --> API[FastAPI Backend]

    subgraph Environmental Pipeline
        API --> DM[Data Manager + TTL Cache]
        DM -->|Tier 1| WAQI[WAQI / CPCB Feed]
        DM -->|Tier 1b| OAQ[OpenAQ v3]
        DM -->|Tier 2| CAMS[Open-Meteo CAMS]
        DM --> CPCB[CPCB NAQI & Sub-Index Calculator]
    end

    subgraph Forecast & Map
        API --> AW[Best Air Window Engine]
        AW --> CAMS
        API --> MAP[Pollutant Map Service]
        MAP --> WAQI
    end

    subgraph Intelligence & Safety
        API --> SE[Deterministic Safety Engine]
        SE --> AI[AI Manager]
        AI -->|Primary| GROQ[Groq Llama 3]
        AI -->|Backup| GEM[Google Gemini]
        AI -->|Offline| DET[Deterministic Fallback]
        GROQ --> VAL[Post-AI Validator & Guardrails]
        GEM --> VAL
    end
```

---

## 5. Data Sources, AI Architecture & Safety Mechanisms

- **Environmental Data Sources:**
  - **WAQI API:** Ground-station observations aggregating CPCB/SPCB feeds.
  - **OpenAQ API v3:** Secondary open ground-station pollutant telemetry.
  - **Open-Meteo Air Quality (ECMWF CAMS) & Weather APIs:** Hourly pollutant projections and wind speed for Tier 2 fallback and Best Air Window scoring.
- **AI Architecture:** Dual-provider failover (`GroqProvider` -> `GeminiProvider` -> `generate_deterministic_fallback_plan`). Model IDs (`GROQ_MODEL_ID`, `GEMINI_MODEL_ID`) are configurable via environment variables.
- **Safety & Scientific Mechanisms:**
  - **CPCB NAQI vs. Indicative Sub-Index:** Official NAQI requires $\ge 3$ pollutants (including $PM_{2.5}$ or $PM_{10}$) with 24h/8h completeness; hourly snapshots are transparently labeled `indicative_particulate_subindex` or `atmospheric_model_estimate`.
  - **Pre- & Post-AI Deterministic Guardrails:** `SafetyEngine` (`CPCB 2014`, `MoHFW NPCCHH 2019`, `WHO 2021`, `ICMR`) bounds prompts before LLM inference, and `validate_and_guardrail_ai_plan()` overrules unsafe outdoor exertion, strips unauthorized medical prescriptions, removes unconditional "safe hour" claims, and contextualizes N95 advice to prolonged open transit.
  - **No Indoor Sensor Fabrication:** Indoor guidance provides behavioral mitigation without claiming to measure indoor AQI.

---

## 6. API Endpoint Overview

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status, version, timestamp, and active model IDs. |
| `GET` | `/api/v1/cities` | Returns metadata and coordinates for the 6 supported Indian metro cities. |
| `GET` | `/api/v1/air-quality?city={id}` | Normalized 8-pollutant telemetry with 3-tier fallback and data provenance. |
| `GET` | `/api/v1/map/pollutants?city={id}&pollutant={p}` | Station-level distribution for `pm25, pm10, no2, so2, o3, co, nh3, pb` (HTTP 400 on invalid parameter). |
| `GET` | `/api/v1/air-window?city={id}&activity={act}` | Multi-pollutant 24–48h comparative forecast windows and hourly series. |
| `POST` | `/api/v1/plan/generate` | Generates personalized 3-period daily routine grounded in live telemetry, forecast window, and safety rules. |

---

## 7. Technology Stack

- **Frontend:** Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS, Recharts, Leaflet + OpenStreetMap, Lucide Icons, Vitest + Testing Library.
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, HTTPX (async), Pytest.
- **Deployment:** Vercel (frontend via `frontend/vercel.json`) & Render (Dockerized backend via `backend/Dockerfile` and `render.yaml`).

---

## 8. Installation, Environment Setup & Local Execution

### Prerequisites
- Python 3.11+
- Node.js 20+
- Server-side API keys: `WAQI_API_TOKEN`, `OPENAQ_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`

### 1. Environment Configuration
Copy `.env.example` to `.env` in the repository root and set your server-side keys:
```bash
cp .env.example .env
```
*(Keep `.env` untracked; never place private API keys in `NEXT_PUBLIC_*` frontend variables.)*

### 2. Run Backend (FastAPI)
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate | macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Run Frontend (Next.js)
```bash
cd frontend
npm install
# Set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 in frontend/.env.local if needed
npm run dev
```
Open `http://localhost:3000`.

---

## 9. Testing & Verification Instructions

```bash
# Backend offline unit & API integration suite (deterministic, mocks external APIs)
cd backend
pytest -v

# Optional live integration tests (requires internet & configured API tokens)
RUN_LIVE_INTEGRATION_TESTS=1 pytest tests/test_live_integration.py -v

# Frontend automated tests, TypeScript check, ESLint & production build
cd frontend
npm test
npx tsc --noEmit
npm run lint
npm run build
```

---

## 10. Assumptions & Known Limitations

- Hourly real-time station feeds on free-tier endpoints do not provide continuous 24-hour historical series, so live snapshots report `indicative_particulate_subindex` or `provider_index` rather than an official 24-hour CPCB NAQI.
- **WAQI Semantics:** WAQI `/feed/` endpoints expose normalized **US-EPA AQI** values and sub-indices (`iaqi`) rather than raw `µg/m³` or `mg/m³` mass concentrations. BreatheWise AI intentionally preserves WAQI values as `"US-EPA Sub-Index"` (`provider_index`) without converting them through CPCB concentration breakpoints or fabricating raw concentrations.
- **Map Caching & Freshness:** `MapService` caches raw city-scoped station snapshots in bounded LRU/TTL memory (600s default) with in-flight request coalescing so switching pollutant tabs reuses cached station data without refetching WAQI, while preserving individual station timestamps and freshness (`live` vs `stale`).
- **Rate Limiting & Trusted-Proxy Boundary:** `POST /api/v1/plan/generate` enforces an in-memory per-IP sliding-window limit (10 requests / 60s, returning `HTTP 429` with `Retry-After`). Forwarding headers (`True-Client-IP`, `CF-Connecting-IP`, `X-Forwarded-For`) are trusted **only** when `TRUST_PROXY_HEADERS=true` (configured in `render.yaml` for Render's Cloudflare edge) or when the peer matches `TRUSTED_PROXY_CIDRS`; otherwise socket peer IP is used so clients cannot spoof forwarding headers. Because rate-limit state lives in process memory, counts reset on restart and do not synchronize across multiple workers (multi-replica deployments require Redis).
- **Required Production CORS Configuration:** `ALLOWED_ORIGINS` rejects wildcard `*` entries and fails closed (`[]`) if unset/empty; production Render deployments must explicitly include `https://breathewiseai-frontend.vercel.app`.
- Open-Meteo CAMS forecasts operate at regional atmospheric grid resolution (~11–40 km) and do not capture hyper-local roadside or construction spikes.
- Free-tier LLM rate limits (e.g., Groq HTTP 429) trigger automatic failover to Gemini or the deterministic Python routine generator.
- Free-tier Render instances spin down during inactivity, causing an initial cold-start latency (~15–40s) on the first request after idle periods.
