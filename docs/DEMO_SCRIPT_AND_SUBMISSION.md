# BreatheWise AI — Demo Script & Hackathon Submission Artifacts

## 1. 3–5 Minute Demo Script

### [0:00 – 0:45] The Urban Air Pollution Problem
- **Hook:** "In Indian metro cities like Delhi, Kolkata, or Mumbai, air quality changes dramatically hour by hour and neighborhood by neighborhood. Yet most apps only show a single city-wide number without telling a family *when* to commute, *how* to manage indoor cooking vs. window ventilation, or *why* a forecast shouldn't be mistaken for 'safe air'."
- **Show:** Open BreatheWise AI dashboard (`http://localhost:3000`) on **Delhi NCR**.

### [0:45 – 1:30] Multi-City Dashboard & Data Provenance
- **Show:** Point out the **Air Quality Hero**, **Provenance Banner**, and **8-Pollutant Grid** ($PM_{2.5}, PM_{10}, NO_2, SO_2, CO, O_3, NH_3, Pb$).
- **Highlight:** Explain the 3-tier pipeline (WAQI/CPCB ground stations -> OpenAQ -> Open-Meteo CAMS model fallback) and how BreatheWise AI transparently distinguishes an **Indicative Real-Time Sub-Index** from an official 24-hour CPCB NAQI without ever fabricating missing pollutants.
- **Action:** Switch between **Delhi NCR** (Poor), **Kolkata** (Very Poor), and **Bengaluru** (Good) to show live adaptation.

### [1:30 – 2:15] Interactive Pollutant Distribution Map
- **Show:** Scroll to the **Pollutant Map** (Leaflet + OpenStreetMap).
- **Action:** Toggle between **PM2.5** and **NO2**. Point out the reporting station count (e.g., `7 / 9` stations in Bengaluru reporting PM2.5), click a station marker to show exact coordinates, provider provenance, and stale vs. live telemetry status.

### [2:15 – 3:00] Best Air Window Engine (Day 3 Highlight)
- **Show:** Scroll to the **Best Air Window Engine — Hourly Forecast** chart (Recharts).
- **Action:** Toggle activity pills (*Running*, *Walking*, *Home Ventilation*) and click *"Show PM2.5, PM10 & O3 traces"*.
- **Highlight:** Point out the `"Lowest Forecast Pollution Period"` vs. `"Higher Pollution Period"`. Emphasize the public-health guardrail: in Very Poor/Severe air (`E(t) > 300`), strenuous outdoor cardio is automatically marked **Restricted (Shift Indoors)** even during the lowest window of the day.

### [3:00 – 3:55] Personalized Household Planner & Dual-LLM Failover
- **Show:** Scroll to **Household Profile & Daily Context**.
- **Action:** Select *"Delhi NCR Family"* (child with asthma, 2-wheeler commute, exhaust fan) and click **Generate Daily Routine**.
- **Highlight:** Show the 3-period routine (Morning, Afternoon, Evening) aligned with the Best Air Window, Indian indoor intelligence (wet mopping/*pocha* vs dry sweeping/*jharoo*, kitchen *tadka* exhaust), and sustainable mobility trade-offs. Mention that Groq Llama 3 runs as primary, with automatic Google Gemini backup and a deterministic Python safety fallback if both APIs fail.

### [3:55 – 4:15] Closing & Safety Safeguards
- **Wrap-up:** "BreatheWise AI combines live environmental telemetry, deterministic CPCB/MoHFW guardrails, and resilient multi-provider AI—built as a trustworthy public-health assistant, not just a hackathon demo."

---

## 2. Technical Summary (For Submission Form)

**BreatheWise AI** is a full-stack urban air-quality and exposure-reduction assistant designed for Indian metropolitan cities. Built with **Next.js (TypeScript, Tailwind CSS, Recharts, Leaflet)** and **FastAPI (Python, Pydantic v2)**, it ingests real-time telemetry via a 3-tier pipeline (WAQI, OpenAQ v3, Open-Meteo CAMS) and computes CPCB sub-indices with strict provenance tracking. A deterministic **CPCB/MoHFW Safety Engine** enforces public-health constraints before and after a dual-provider GenAI planner (**Groq Llama 3** primary, **Google Gemini** backup, plus offline Python fallback). Its **Best Air Window Engine** evaluates 24–48h multi-pollutant CAMS forecasts to identify comparatively lower exposure periods while blocking unsafe strenuous outdoor exertion during Very Poor or Severe conditions.

---

## 3. LinkedIn Project Post Draft

> Excited to share **BreatheWise AI**, built for PromptWars Virtual Challenge 6!
>
> Most air-quality apps stop at a single AQI number. In Indian metros like Delhi, Mumbai, Bengaluru, Hyderabad, Kolkata, and Chennai, residents need actionable, honest answers: *When is the comparatively lowest pollution window for a commute? Should I open windows if someone is cooking indoors? And when should outdoor exercise move inside?*
>
> What we engineered in BreatheWise AI:
> - **Zero-Fabrication 3-Tier Telemetry:** Ground station data (WAQI / OpenAQ) with Open-Meteo CAMS model fallback, preserving station provenance, freshness, and official vs. indicative CPCB index distinctions.
> - **Multi-Pollutant Best Air Window Engine:** 24–48h hourly CAMS forecast scoring across PM2.5, PM10, O3, NO2, SO2, and CO with interactive Recharts visualizations.
> - **Deterministic Safety Guardrails + Dual-LLM Failover:** CPCB & MoHFW rules validate every AI-generated routine (Groq Llama 3 -> Google Gemini -> pure-Python fallback) so unsafe outdoor cardio is never recommended during severe pollution.
> - **Interactive Pollutant Map:** Real monitoring station grids built with Leaflet & OpenStreetMap.
>
> #AI #FastAPI #NextJS #PublicHealth #CleanAir #AirQuality #PromptWars #Python #TypeScript
