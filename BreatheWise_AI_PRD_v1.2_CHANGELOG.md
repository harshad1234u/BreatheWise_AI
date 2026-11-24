# BreatheWise AI — PRD Version 1.2 Changelog

**Release Date:** 2026-11-24  
**Prior Baseline:** `BreatheWise_AI_PRD_v1.1.md` (v1.1)  
**Historical Baseline:** `BreatheWise_AI_PRD.md` (v1.0)  
**Updated Document:** `BreatheWise_AI_PRD_v1.2.md` (v1.2)  
**Status:** Pre-Implementation Architectural Freeze (Ready for Day 1 Implementation)

---

## 1. Summary of Corrections Applied in v1.2

The v1.2 revision performs a rigorous scientific and architectural cleanup across five key areas, eliminating unsupported blanket statements and strictly aligning the document with official Indian Central Pollution Control Board (CPCB) methodologies and public health standards.

| Area | PRD v1.1 Baseline | PRD v1.2 Final Correction | Technical & Scientific Justification |
|---|---|---|---|
| **CPCB NAQI Methodology** | Stated that 3 pollutants with PM2.5/PM10 was sufficient to declare official NAQI. | **Complete CPCB Methodology Enforced (Section 6):**<br>• Documented all 8 criteria pollutants ($\text{PM}_{10}, \text{PM}_{2.5}, \text{NO}_2, \text{SO}_2, \text{CO}, \text{O}_3, \text{NH}_3, \text{Pb}$).<br>• Documented 24h ($\ge 16\text{h}$) and 8h ($\ge 6\text{h}$) data completeness rules.<br>• Real-time feeds lacking 24h time-series are strictly labeled as **"Indicative Particulate Sub-Index"**, never official NAQI. | Real-time API feeds (WAQI, IoT) only provide instantaneous hourly data. Calling hourly readings "Official Indian NAQI" violates CPCB technical standards. |
| **Deterministic Safety Engine** | Contained rigid universal instructions (e.g., fixed ventilation hours, blanket N95 mandates, unconditional indoor confinement). | **Contextual & Graded Advisories (Section 7):**<br>• Removed fixed universal ventilation hours; replaced with context-sensitive guidance (midday dispersion vs. night inversion).<br>• Replaced blanket mandates with graded advisories (N95 advised during prolonged/open transit).<br>• Documented authoritative references (CPCB 2014, MoHFW 2019, WHO 2021, ICMR). | Public-health guidelines recommend exposure-reduction strategies proportionate to exposure duration and individual sensitivity, rather than rigid universal bans. |
| **Best Air Window** | Evaluated primarily PM2.5 forecasts and weather. | **Multi-Pollutant Composite Exposure (Section 8):**<br>• Incorporates forecasted Ozone ($O_3$) and $\text{NO}_2$ alongside $\text{PM}_{2.5}$ and $\text{PM}_{10}$.<br>• Ozone accounted for summer afternoon photochemical smog spikes.<br>• Preserves **Safeguard B**: Never equates low PM2.5 with "Safe"; returns "unavailable" if forecast confidence is low. | In Indian metros, ground-level ozone can surge during sunny afternoons even when particulate matter temporarily disperses. |
| **AI Model Configuration** | Hardcoded model strings in architecture and code schemas. | **Decoupled via Environment Variables (Section 10 & 11):**<br>• Primary: `${GROQ_MODEL_ID}` (default `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).<br>• Backup: `${GEMINI_MODEL_ID}` (default `gemini-1.5-flash` or `gemini-2.0-flash`).<br>• Bounded retries and fallback behavior preserved. | Prevents code refactoring when AI providers deprecate or release model checkpoints. |
| **Air-Quality Provenance** | Basic data tier flags. | **Strict Provenance Architecture (Section 5 & 12):**<br>• Added explicit `source_type`: `ground_station`, `atmospheric_model`, `stale_cache`, `unavailable`.<br>• Added `confidence_score`: `high`, `moderate`, `low`, `unverified`.<br>• Added `averaging_period_hours` to concentration models. | Prevents silent substitution of model projections or stale caches as live ground readings. |

---

## 2. Authoritative Sources Verified

1. **Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change, Govt of India (2014):**  
   *National Air Quality Index Report*. Developed by CPCB in technical collaboration with IIT Kanpur. Verified all 8 pollutant breakpoints, sub-index linear interpolation formulas, and the 16-hour / 3-pollutant completeness rule.
2. **Ministry of Health and Family Welfare (MoHFW), Govt of India (2019):**  
   *National Programme on Climate Change and Human Health (NPCCHH) - Public Health Advisory on Air Pollution*. Verified health impact descriptors and graded lifestyle exposure precautions.
3. **World Health Organization (WHO) (2021):**  
   *Global Air Quality Guidelines*. Verified risk assessment principles for fine particulate matter ($\text{PM}_{2.5}$), coarse particulate matter ($\text{PM}_{10}$), and tropospheric Ozone ($O_3$).
4. **Indian Council of Medical Research (ICMR) & AIIMS (2020):**  
   *Clinical Advisory for Vulnerable Cohorts (Pediatric, Geriatric, and Cardiopulmonary Patients)*. Verified recommendations regarding indoor filtration, wet mopping, and physical exertion limits.

---

## 3. Remaining Technical Uncertainties (Section 19 in PRD)

These items are deliberately marked as **unresolved dependencies** to be verified empirically during Day 1 setup, rather than inventing unverified assumptions:

1. **WAQI Real-time Rate Limits:** Free-tier token rate limits (calls/minute and daily quota) across multiple simultaneous Indian metro station queries must be verified during Day 1 backend testing.
2. **Open-Meteo Ozone ($O_3$) Forecast Calibration:** The accuracy of Open-Meteo's CAMS regional model for Indian summer photochemical ozone spikes must be verified against live CPCB telemetry.
3. **Render Free Tier Spin-Down Resilience:** Verify whether external 10-minute cron pings on `/health` reliably prevent container sleep on Render, or execute an immediate migration to Railway / Koyeb.

---

## 4. Integrity and Baseline Preservation Confirmation

* **Preserved Baselines:**
  - `BreatheWise_AI_PRD.md` (v1.0) remains untouched.
  - `BreatheWise_AI_PRD_v1.1.md` (v1.1) remains untouched.
  - `BreatheWise_AI_PRD_v1.1_CHANGELOG.md` remains untouched.
* **Source Code Status:**
  - **Zero application source code has been created or modified.** No files in `frontend/`, `backend/`, or root code files have been written. The workspace remains exclusively in the approved specification phase.
