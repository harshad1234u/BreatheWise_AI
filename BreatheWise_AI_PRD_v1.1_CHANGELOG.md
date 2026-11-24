# BreatheWise AI — PRD Version 1.1 Changelog

**Release Date:** 2026-11-24  
**Baseline Document:** `BreatheWise_AI_PRD.md` (v1.0)  
**Updated Specification:** `BreatheWise_AI_PRD_v1.1.md` (v1.1)  
**Status:** Approved for Implementation

---

## Executive Summary of Changes

The transition from PRD v1.0 to v1.1 upgrades BreatheWise AI from a hackathon concept into a **production-grade, resilient, and scientifically responsible application architecture**. The revision directly incorporates the findings from the comprehensive technical audit, resolves single-point-of-failure data risks, enforces strict public-health safety boundaries via deterministic code, and eliminates user onboarding friction.

---

## 1. Architectural & Functional Changes Comparison

| Dimension / Component | PRD v1.0 (Baseline Prototype) | PRD v1.1 (Production-Ready Architecture) | Technical Rationale & Impact |
|---|---|---|---|
| **Air Quality Data Ingestion** | Relied vaguely on "CPCB where accessible" + OpenAQ. | **Formalized 3-Tier Ingestion Pipeline:**<br>• Tier 1: WAQI API (primary ground aggregator for CPCB/SPCB) + OpenAQ v3.<br>• Tier 2: Open-Meteo CAMS atmospheric model fallback.<br>• Tier 3: Deterministic unavailable / stale state. | CPCB has no public unauthenticated REST API; scraping is fragile. WAQI programmatically ingests CPCB monitors. Open-Meteo provides resilient fallback when ground telemetry is dormant. |
| **AQI Interpretation & Methodology** | Assumed provider AQI was directly comparable. | **Explicit Indian NAQI Engine (Safeguard A):**<br>• Strict CPCB linear breakpoint formula applied to raw concentrations.<br>• Particulate-only data explicitly labeled as a sub-index, not a complete multi-pollutant NAQI.<br>• Clear disclosure of missing pollutants. | US EPA and Indian NAQI have incompatible sub-index breakpoints. Calculating NAQI internally standardizes public-health interpretation across all sources. |
| **Location Granularity** | Generic city-level dropdown. | **Hierarchical Location Model:**<br>• City selection (P0).<br>• Locality and monitoring station selection (P1).<br>• Station distance indicators when permitted. | Indian metropolitan air quality is radically hyperlocal (e.g., Anand Vihar vs Lodhi Road in Delhi). City-wide averages can mislead residents. |
| **Safety Engine & AI Boundaries** | Relied primarily on the LLM prompt instructions to "be safe". | **Deterministic Safety Rules Engine:**<br>• Hard public-health constraint matrix computed in Python before AI generation.<br>• Post-AI validation hook sanitizes any LLM output violating constraints.<br>• LLM restricted to scheduling, explanations, and personalization. | Generative LLMs cannot be trusted with life-safety calculations. Public-health boundaries must be deterministic and testable. |
| **New Feature: Best Air Window** | Not present in v1.0. | **Introduced "Best Air Window" (P1):**<br>• Identifies `ventilation_window`, `safe_outdoor_window`, and `peak_hazard_window`.<br>• Computed via Open-Meteo 24h forward projection.<br>• Enforces **Safeguard B**: Never labels a severe window "safe"; uses "comparatively better window". | Gives users proactive, schedule-oriented guidance (*when* to open windows or run errands) instead of static number anxiety. |
| **Indoor Air Intelligence** | Generic ventilation and filter advice. | **Indian Household Intelligence (P0):**<br>• Wet mopping (*pocha*) vs dry sweeping (*jharoo*) for $\text{PM}_{10}$ control.<br>• High-heat *tadka* / frying emission management.<br>• Kitchen exhaust fan & door management.<br>• Debunking of plant-based purification myths. | Western HVAC advice does not fit Indian urban apartments. Contextual indoor practices offer immediate, realistic value to households. |
| **User Onboarding & Authentication** | Presumed Supabase Auth as standard path. | **Guest-First / Local-First Architecture:**<br>• P0: 100% usable via browser `localStorage` without registration.<br>• P1: Optional Supabase Auth for cross-device synchronization.<br>• Minimal enums for health sensitivities; zero clinical PII. | Mandatory sign-up causes 60%+ user drop-off and frustrates hackathon evaluators. Guest-first enables instant value in 5 seconds. |
| **AI Caching Strategy** | Unspecified. | **Strict Segregation:**<br>• Raw environmental observations cached globally for 30–45 mins.<br>• **Zero cross-user caching of personalized plans.**<br>• Browser-local caching for repeat client visits. | Caching personalized plans across users creates high risk of leaking private household routines, family member names, or commute timings. |
| **AI Failover Strategy** | Groq primary, Gemini backup (conceptual). | **Engineered Failover Matrix:**<br>• Groq Llama 3 (primary, <800ms).<br>• Gemini 1.5/2.0 Flash (failover on 429, 5xx, or >4.5s timeout).<br>• Deterministic fallback plan if both AI services fail.<br>• Common Pydantic validation schema. | Ensures the application never crashes or displays a blank screen during provider outages or rate limits. |
| **Infrastructure & Cold Starts** | Render backend without latency mitigation. | **Cold-Start Resilience Strategy:**<br>• Automated health-pinger on `/health` via external cron.<br>• Frontend warming indicator on initial page load.<br>• Evaluation criteria for Railway/Koyeb zero-sleep hosting. | Render free tier sleeps after 15 minutes, causing a 50–90s cold start that ruins live demonstrations and user experience. |

---

## 2. Incorporation of the Three Mandatory Safeguards

### Safeguard A: AQI Accuracy & Methodology
- **Problem in v1.0:** External provider AQIs were accepted at face value, conflating US EPA scales with Indian standards or treating particulate-only estimates as official NAQI.
- **Implementation in v1.1 (Section 6):**
  - Incorporated the official CPCB linear interpolation formula.
  - Mandated that if fewer than 3 pollutants are present, the index **must** be rendered as *"Calculated Particulate Sub-Index"* rather than the official *"Indian National AQI"*.
  - Added the `methodology_disclosure` field to the Pydantic schema to provide full mathematical transparency in the UI.

### Safeguard B: Forecast Interpretation & Nuanced Terminology
- **Problem in v1.0:** Standard algorithms label the lowest diurnal PM2.5 period as "Safe", which is dangerous when the minimum PM2.5 is still $140\,\mu\text{g/m}^3$ (Very Poor).
- **Implementation in v1.1 (Section 8):**
  - Enforced that if air quality remains in Poor, Very Poor, or Severe bands, the UI must use the terms **"Comparatively Better Window"** or **"Lowest Exposure Window"**, accompanied by an explicit advisory note.
  - Windows are set to `null` with a clear explanation if hourly forecast data is unavailable.

### Safeguard C: Source-Backed Public-Health Recommendations
- **Problem in v1.0:** LLM generation risks emitting rigid medical mandates or unsupported absolutes (e.g., "mandatory N95 indoors", "never leave the home").
- **Implementation in v1.1 (Section 7 & 17):**
  - Replaced LLM safety autonomy with the **Deterministic Safety Matrix** mapped to official CPCB health categories.
  - Added a post-AI validation filter that intercepts and sanitizes any generated recommendation violating safety bounds.
  - Incorporated a mandatory, prominent non-medical public-health advisory in the application footer and plan modals.

---

## 3. Scope & Prioritization Alignment

To ensure 100% feasibility within the 3-day development timeline, features have been strictly partitioned:
- **P0 (Mandatory Core):** Multi-tier ingestion, Indian NAQI calculator, guest-first onboarding with 3 sample evaluator profiles, deterministic safety engine, Groq/Gemini failover, 3-period daily planner, Indian indoor intelligence, and error indicators.
- **P1 (High-Value Enhancements):** Best Air Window, locality/station selector, optional Supabase login, 24-hour visual trend charts, and weather context.
- **P2 (Postponed):** Interactive GIS maps, voice assistant, and SMS/WhatsApp notifications.

---

## 4. Integrity Verification

- **Baseline Preserved:** `BreatheWise_AI_PRD.md` remains completely unmodified as the v1.0 historical baseline.
- **No Code Modified:** Zero application source code was created or edited during this documentation phase.
- **Actionability:** `BreatheWise_AI_PRD_v1.1.md` contains complete Pydantic data schemas, SQL tables, API specifications, and Mermaid diagrams ready for systematic execution.
