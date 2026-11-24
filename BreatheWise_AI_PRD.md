# BreatheWise AI — Product Requirements Document (PRD)

**Version:** 1.0  
**Status:** Development baseline  
**Project:** PromptWars Virtual — Challenge 6: Urban Air Quality Assistant  
**Product type:** GenAI-powered, responsive web application  
**Primary objective:** Help people and households understand current outdoor air quality and make practical, pollution-aware daily decisions.

---

## 1. Product summary

BreatheWise AI is a household-focused Urban Air Quality Assistant. It combines verified outdoor air-quality measurements, weather context, household preferences and an AI recommendation layer to produce understandable, actionable daily guidance.

The product must not be a static AQI dashboard or a generic chatbot. It must help users decide what to do, when to do it, and why a recommendation is relevant to their household.

### Product principles

1. **Data before AI:** AQI and pollutant measurements must come from a real data source, never be invented by an LLM.
2. **Personalized guidance:** Recommendations must consider the user's household profile and daily routine.
3. **Explainable recommendations:** Each recommendation should include a reason and the data context behind it.
4. **Safety-first:** AI output is advisory, not a medical diagnosis or emergency service.
5. **Honest uncertainty:** Missing, stale, unavailable or low-confidence data must be clearly disclosed.
6. **Useful in a demo:** Provide clearly labelled sample profiles and a reliable evaluator walkthrough without presenting sample measurements as live data.

---

## 2. Problem statement

Urban residents often see air-quality numbers but do not know how to translate them into daily decisions. Families need practical guidance about outdoor activity, commuting, ventilation, indoor pollution reduction and sustainable alternatives. Generic advice does not account for differences between children, older adults, students, athletes and working professionals.

BreatheWise AI addresses this gap by connecting live outdoor measurements with household context and producing a practical daily plan.

---

## 3. Goals and non-goals

### 3.1 Goals

- Support selection of multiple Indian cities; do not hardcode a single city.
- Retrieve real outdoor AQI where an authoritative source is available, plus PM2.5 and PM10 measurements.
- Display source, monitoring station where available, measurement time and retrieval time.
- Collect a minimal household and lifestyle profile with user consent.
- Generate morning, afternoon and evening recommendations.
- Cover all three challenge pillars:
  1. Low-emission daily routines.
  2. Indoor air-quality guidance.
  3. Sustainable alternatives with impact explanations.
- Use Groq as the primary LLM provider and Google Gemini as automatic backup.
- Include sample profiles for quick evaluator testing.
- Deploy a working application and provide source code, LinkedIn build explanation and screen-recorded demo.

### 3.2 Non-goals for the three-day build

- Medical diagnosis, treatment advice or individual disease-risk prediction.
- Guaranteed personal exposure measurement.
- Live indoor sensor integration or IoT hardware.
- Route-level pollution modelling unless reliable data is available.
- Complex user social network, gamification or community feed.
- Native Android/iOS applications.
- Voice assistant.
- Claims of exact health outcomes or exact emissions reductions without a defensible calculation method.

---

## 4. Target users and personas

### Persona A — Parent / household with children
Needs to decide whether children should play outdoors, how to manage school commutes and how to reduce indoor dust and smoke exposure.

### Persona B — Senior citizen / vulnerable household member
Needs cautious, clear recommendations and reminders to avoid strenuous outdoor activity during poor air conditions. Do not infer a medical condition.

### Persona C — Student / athlete
Needs help planning sports, walking, running and campus travel around current air conditions.

### Persona D — Working professional
Needs commute-aware suggestions, practical scheduling and lower-emission travel alternatives.

### Persona E — General resident
Needs a quick explanation of local air conditions and simple actions that can be taken today.

---

## 5. Scope and feature requirements

Priority definitions:
- **P0:** Must work for a valid submission.
- **P1:** Strongly recommended if time permits.
- **P2:** Optional; do not delay P0 work.

### 5.1 City selection and live air intelligence — P0

**Requirements**
- Allow a user to select from multiple Indian cities.
- Support city search or a maintained city list.
- Fetch available AQI and pollutant observations from configured providers.
- Prefer CPCB/official Indian AQI data when a legitimate, accessible integration is available.
- Use OpenAQ for pollutant measurements and supplementary coverage.
- Do not call an OpenAQ PM2.5 value an official CPCB AQI.
- Display:
  - AQI and category only when a valid AQI value and methodology/source are available.
  - PM2.5 and PM10 with units (µg/m³).
  - Station name/location when supplied.
  - Observation timestamp.
  - Data provider.
  - Last fetched timestamp.
  - Data status: live, stale, partial, unavailable or sample.
- Cache provider responses to reduce latency and unnecessary API calls.
- Preserve source metadata with stored observations.

**Acceptance criteria**
- A user can select at least two supported Indian cities.
- The dashboard shows actual provider data or an explicit unavailable state.
- The UI never silently substitutes fabricated or sample values for live data.
- The user can distinguish official AQI, pollutant concentration and any locally calculated AQI.

### 5.2 Household profile — P0

**Inputs**
- Display name or household label (optional).
- City.
- Household members / age groups (avoid collecting exact birth dates).
- Optional vulnerability preferences, voluntarily supplied by the user.
- Persona: parent, student, athlete, professional, senior citizen or general.
- Routine: commute, school, work or outdoor exercise time windows.
- Indoor equipment and context, such as air purifier availability and cooking ventilation.

**Requirements**
- Ask only for information needed to personalize recommendations.
- Make sensitive health-related inputs optional.
- Explain why profile details are requested.
- Allow editing and deletion of profile data.
- Provide a sample household profile that requires no personal data.

**Acceptance criteria**
- A user can create, view and update a profile.
- A plan uses the selected profile fields.
- The app remains usable when optional profile fields are omitted.

### 5.3 AI daily routine planner — P0

**Requirements**
- Generate a morning, afternoon and evening plan.
- Inputs must include validated air data, data freshness, city, weather context if available, household profile and routine.
- Recommendations should be actionable, specific and concise.
- Each recommendation should include:
  - Suggested action.
  - Time period.
  - Reason.
  - Data context used.
  - Confidence or limitation note when appropriate.
- If no valid current data exists, the model must not pretend it has current conditions. Provide general precautionary guidance clearly labelled as such, or ask the user to retry.

**Acceptance criteria**
- A valid profile and valid data produce a structured plan.
- Plan output is validated against a schema before display.
- The plan contains all three time periods or explicitly marks a period as not applicable.
- AI output cannot overwrite the measured AQI or pollutant values.

### 5.4 Indoor Air Guardian — P0

**Requirements**
- Provide practical guidance for ventilation timing, dust reduction, cooking smoke management and air purifier use where relevant.
- Tailor guidance to the household's stated equipment and context.
- Do not claim indoor AQI is known unless an indoor sensor measurement is actually connected.
- Do not recommend indoor plants as a substitute for filtration or ventilation controls.
- Explain that outdoor readings alone cannot establish indoor air quality.

**Acceptance criteria**
- Guidance is available from current conditions and profile context.
- The interface labels it as guidance, not a measured indoor reading.
- Advice does not make unsupported claims about plant-based air purification.

### 5.5 Sustainable alternatives — P0

**Requirements**
- Suggest practical alternatives such as public transport, trip consolidation, walking/cycling when appropriate and lower-emission mobility.
- Do not recommend walking or cycling outdoors during unsafe pollution conditions merely because they are low-emission.
- Explain trade-offs between personal exposure and emissions.
- Quantify avoided emissions only when a documented calculation method and required inputs exist. Otherwise use qualitative explanations.

**Acceptance criteria**
- At least one relevant alternative is shown when appropriate.
- Each alternative explains why it is suggested.
- No unsupported numeric savings are displayed.

### 5.6 Ask BreatheWise — P1

**Requirements**
- Contextual chat grounded in current validated data and the household profile.
- The assistant must disclose when information is missing or stale.
- Do not let the chat invent live AQI, weather, station information or health facts.
- Keep responses within the product's safety boundaries.

### 5.7 Impact tracker and history — P1

**Requirements**
- Store timestamped air observations and generated plans where user consent and retention policy allow.
- Show trends only when enough historical data exists.
- Distinguish observed measurements from estimates.
- Avoid presenting plan adherence as a measured reduction in personal exposure.

### 5.8 Maps — P2

- Add a map only when station coordinates and licensing/usage terms are suitable.
- Show station markers with source and timestamp.
- Do not imply a station reading represents every street or neighbourhood.

---

## 6. AI provider strategy

### Primary and fallback

- **Primary:** Groq API.
- **Backup:** Google Gemini API.
- Both providers must implement the same internal interface and return the same validated response schema.
- Provider choice must remain server-side.

### Fallback rules

Attempt Gemini fallback for:
- Connection timeout after a bounded primary attempt.
- HTTP 429 rate limit, respecting `Retry-After` where supplied.
- HTTP 5xx provider/server failures.
- Provider service unavailability.

Do not blindly fallback/retry for:
- HTTP 400 malformed request or invalid schema.
- HTTP 401/403 invalid credentials or permission errors.
- Missing required application inputs.
- Invalid or stale air-quality data.

Use bounded retries, explicit request timeouts and structured logs. Avoid retry storms. If both providers fail, show a clear temporary-unavailable state and preserve non-AI measured data.

### AI response schema (illustrative)

```json
{
  "provider": "groq",
  "generated_at": "ISO-8601 timestamp",
  "data_context": {
    "city": "Chennai",
    "air_data_status": "live",
    "source": "provider name",
    "observed_at": "ISO-8601 timestamp"
  },
  "daily_plan": {
    "morning": [
      {
        "action": "Actionable recommendation",
        "reason": "Why this is recommended",
        "caution": "Relevant limitation or null"
      }
    ],
    "afternoon": [],
    "evening": []
  },
  "indoor_guidance": [],
  "sustainable_alternatives": [],
  "limitations": []
}
```

This is a target response contract, not a claim that either provider will always return valid JSON. Parse and validate every response; reject or safely repair only through a controlled validation process.

### Prompting rules

- Supply the exact measured values, units, source and observation time.
- Explicitly instruct the model not to create or alter measurements.
- Tell the model to state when inputs are missing or stale.
- Request structured JSON matching the response schema.
- Treat user-provided text and external data as untrusted input.
- Do not put API keys or secrets in prompts.
- Never allow model output to execute code, SQL or arbitrary tools.

---

## 7. External integrations

| Integration | Purpose | Implementation notes |
|---|---|---|
| CPCB / official source | Official Indian AQI | Use only a legitimate accessible endpoint or approved data access method; do not assume dashboard pages are public APIs. |
| OpenAQ API v3 | Pollutant observations | API key may be required; preserve station, parameter, unit and timestamp. |
| Groq API | Primary AI inference | Server-side only; configure a supported model. |
| Google Gemini API | AI fallback | Server-side only; configure a supported model. |
| Open-Meteo | Weather context | Optional; use only if forecast data improves a recommendation. |
| Supabase | Database and authentication | Enable Row Level Security for user-owned data. |
| OpenStreetMap/Nominatim | Geocoding/map context | Optional; respect usage policies and rate limits. |

Do not treat every provider as interchangeable. AQI indices, pollutant concentrations, units, averaging periods and station coverage differ.

---

## 8. Technical architecture

### Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| Backend | FastAPI + Python |
| Validation | Pydantic |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth (optional for demo if time is limited) |
| Primary AI | Groq |
| Backup AI | Google Gemini |
| Air data | CPCB where accessible + OpenAQ |
| Weather | Open-Meteo (optional) |
| Charts | Recharts |
| Maps | Leaflet + OpenStreetMap (optional) |
| Frontend deployment | Vercel |
| Backend deployment | Render |
| Version control | Git + GitHub |
| Development environment | Google Antigravity, subject to current challenge rules |

### Request flow

1. User selects a city and household profile.
2. Frontend calls FastAPI.
3. Backend fetches/caches air-quality data and optional weather context.
4. Backend normalizes units, validates timestamps and records provenance.
5. Deterministic rules engine classifies data quality and safety constraints.
6. Backend sends validated context to Groq.
7. If eligible provider failure occurs, backend attempts Gemini.
8. Pydantic validates the AI response.
9. Backend returns measured data and recommendations separately.
10. Frontend displays the plan, data source, timestamp and limitations.

### Suggested repository structure

```text
breathewise-ai/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── features/
│   │   ├── air-quality/
│   │   ├── household/
│   │   ├── planner/
│   │   └── indoor-guidance/
│   ├── lib/
│   └── types/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── air_quality/
│   │   │   ├── weather/
│   │   │   └── ai/
│   │   │       ├── base.py
│   │   │       ├── groq_provider.py
│   │   │       ├── gemini_provider.py
│   │   │       └── ai_manager.py
│   │   ├── rules/
│   │   ├── db/
│   │   └── core/
│   └── tests/
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. Database requirements

Suggested initial tables:

### `profiles`
- `id` (UUID; tied to authenticated user where applicable)
- `display_name`
- `city`
- `persona`
- `routine_preferences` (JSONB)
- `created_at`
- `updated_at`

### `household_members`
- `id`
- `profile_id`
- `age_group`
- `optional_needs` (minimal, user-provided information only)
- `created_at`

### `air_quality_observations`
- `id`
- `city`
- `station_id` (nullable)
- `station_name` (nullable)
- `parameter`
- `value`
- `unit`
- `aqi_value` (nullable)
- `aqi_methodology` (nullable)
- `source`
- `observed_at`
- `fetched_at`
- `data_status`

### `daily_plans`
- `id`
- `profile_id`
- `city`
- `data_observation_ids`
- `provider`
- `plan_json`
- `generated_at`

Use foreign keys, indexes and RLS policies. Do not store API keys in database rows. Do not store unnecessary sensitive profile details.

---

## 10. API endpoint requirements

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/cities` | GET | List supported cities |
| `/api/v1/air-quality` | GET | Retrieve normalized air data for a city |
| `/api/v1/profile` | GET | Read current user's profile |
| `/api/v1/profile` | POST/PUT | Create or update profile |
| `/api/v1/plan/generate` | POST | Generate daily plan |
| `/api/v1/indoor/guidance` | POST | Generate indoor guidance |
| `/api/v1/sustainable` | POST | Generate sustainable alternatives |
| `/api/v1/history` | GET | Retrieve permitted history |
| `/health` | GET | Service health check |

All endpoints must validate inputs, return consistent error objects and avoid exposing provider secrets or raw stack traces.

---

## 11. UI and user experience requirements

### Main screens

1. **Dashboard**
   - City selector.
   - AQI/category when valid.
   - PM2.5 and PM10.
   - Source, station and timestamps.
   - Data freshness/status indicator.
   - Link to daily plan.

2. **Household onboarding**
   - Persona and household composition.
   - Routine preferences.
   - Optional indoor equipment/context.
   - Privacy explanation.

3. **Daily plan**
   - Morning, afternoon and evening.
   - Action, reason and caution.
   - Data context and generated timestamp.

4. **Indoor guidance**
   - Ventilation, filtration, dust and cooking guidance.
   - Explicit statement that indoor AQI is not measured without a sensor.

5. **Sustainable choices**
   - Alternative actions and trade-offs.
   - Quantified savings only when defensible.

6. **Sample demo mode**
   - Pre-filled household profiles.
   - Clearly marked sample data if used.
   - One-click evaluator journey.

### UI states

Every data-driven component must support:
- Loading.
- Success/live.
- Partial data.
- Stale data.
- No station/data found.
- Provider error.
- AI provider unavailable.
- Invalid response.
- Sample/demo mode.

Use accessible labels, keyboard navigation, sufficient contrast, clear units and mobile-friendly layouts.

---

## 12. Edge cases and required handling

| Edge case | Required behavior |
|---|---|
| City not supported | Explain that data is unavailable; offer another supported city. |
| No nearby monitoring station | Do not invent a local reading; show nearest available station only if distance is known. |
| AQI missing but PM values exist | Show pollutant concentrations; do not fabricate official AQI. |
| PM2.5 missing | Mark PM2.5 unavailable; continue only with valid available inputs. |
| PM10 missing | Mark PM10 unavailable; do not substitute another pollutant. |
| Data timestamp is old | Mark stale; do not call it live. Use a configurable freshness threshold. |
| Provider returns future timestamp | Flag invalid observation and exclude it pending validation. |
| Provider returns different units | Normalize only using a valid conversion; preserve original value/unit for traceability. |
| Providers disagree | Show source-specific readings and timestamps; do not silently average incompatible data. |
| Duplicate observations | Deduplicate using provider/station/parameter/time identity. |
| API rate limit (429) | Respect retry guidance, use cache if still within freshness threshold, otherwise show limitation. |
| Provider outage (5xx/timeout) | Bounded retry, then cache if valid; otherwise unavailable state. |
| Invalid API key (401/403) | Log configuration error safely; do not loop retries or expose credentials. |
| Groq fails | Attempt Gemini for eligible transient failures. |
| Gemini also fails | Show AI unavailable; retain live data and deterministic general guidance. |
| AI returns malformed JSON | Reject response; retry once with constrained correction if safe, otherwise show fallback state. |
| AI invents a measurement | Never display the invented value; render measurements only from backend data objects. |
| AI gives unsafe advice | Apply deterministic validation and block/rewrite unsafe recommendation; show safe general guidance. |
| User has no profile | Offer a general plan or sample profile; label it as non-personalized. |
| Optional profile fields omitted | Continue with available context and state limitations. |
| User enters prompt injection | Treat profile/chat content as untrusted; never let it override system safety rules. |
| No internet connection | Show cached data with timestamp if still valid; otherwise show offline state. |
| Supabase unavailable | Preserve non-personalized read-only functionality where possible; do not pretend profile save succeeded. |
| Unauthorized profile access | Enforce RLS and return 401/403 without leaking data. |
| User deletes profile | Delete or anonymize associated personal data according to the retention policy. |
| Small-screen layout | Use responsive layout and avoid hiding source/timestamp disclosures. |
| Sample data mistaken for live | Persistent DEMO/SAMPLE label; never mix sample and live values without clear separation. |

---

## 13. Safety, privacy and security

### Must do
- Keep Groq, Gemini and data-provider keys on the server.
- Use environment variables and maintain `.env.example` with placeholders only.
- Add `.env` to `.gitignore`.
- Validate all external API responses.
- Apply Supabase RLS to user-owned records.
- Collect minimal profile information and explain optional fields.
- Separate measured facts, estimates and AI-generated guidance.
- Log provider name, latency, status and error category without logging secrets or unnecessary personal data.
- Use HTTPS in deployment.
- Provide clear disclaimers that the application is not a medical service.

### Must not do
- Never expose API keys in browser bundles, GitHub or screenshots.
- Never ask an LLM to guess current AQI or pollutant values.
- Never represent sample values as live.
- Never claim to measure indoor air without a sensor.
- Never diagnose, prescribe medication or guarantee health outcomes.
- Never claim exact emissions/exposure reduction without a documented calculation.
- Never store sensitive health details unnecessarily.
- Never trust model output without schema and safety validation.
- Never silently use stale readings as current readings.

### Suggested user-facing disclaimer

“BreatheWise AI provides general air-quality information and lifestyle guidance based on available data. It is not a medical device and does not replace advice from qualified healthcare or public-health authorities. Air-quality readings may vary by monitoring station and time.”

---

## 14. Testing and quality requirements

### Functional tests
- City selection and unsupported city handling.
- Valid and missing AQI/PM2.5/PM10 values.
- Source and timestamp rendering.
- Profile creation/update and optional fields.
- Daily plan generation.
- Groq success and Gemini fallback.
- Both providers unavailable.
- Malformed AI response.
- Sample mode labeling.

### Security tests
- Verify no secrets in frontend bundles or Git history.
- Verify unauthorized profile reads/writes fail.
- Verify RLS isolation between users.
- Verify malformed user input is rejected.
- Verify error messages do not expose secrets or stack traces.

### Quality gates
- No critical errors in the main evaluator journey.
- No fabricated live data.
- All three challenge pillars demonstrable.
- Main screens usable on desktop and mobile.
- Deployment health endpoints respond.
- README contains setup and demo instructions.

---

## 15. Three-day implementation plan

### Day 1 — Foundation and live data
- Initialize repository and frontend/backend projects.
- Configure Supabase and environment variables.
- Build dashboard shell and city selector.
- Integrate available real air-quality source(s).
- Normalize data and display source/timestamps.
- Implement loading, stale, missing and error states.

**Day 1 exit criteria:** A deployed or locally working dashboard can show real provider observations with provenance, or clearly show that data is unavailable.

### Day 2 — Personalization and AI
- Implement household onboarding and profile persistence.
- Build deterministic data/safety validation.
- Integrate Groq as primary provider.
- Integrate Gemini as backup provider.
- Implement structured daily planner.
- Implement indoor guidance and sustainable alternatives.
- Add sample household profiles.

**Day 2 exit criteria:** A user can select a city, use a household profile and generate a structured personalized plan from validated context.

### Day 3 — Testing, polish and submission
- Add history/impact feature only if P0 features are stable.
- Complete responsive UI and accessibility pass.
- Test provider failure and edge cases.
- Secure environment variables and RLS.
- Deploy frontend and backend.
- Verify public demo.
- Complete GitHub README.
- Record screen demo.
- Publish LinkedIn build-in-public post.
- Verify all required submission links.

**Day 3 exit criteria:** The complete core user journey works on the deployed application and all submission deliverables are ready.

### Feature freeze
Do not start optional maps, voice, complex analytics or new AI features until all P0 acceptance criteria pass.

---

## 16. Required challenge submission deliverables

The Challenge 6 explainer specifies four required items:

1. **Deployed application link:** Publicly accessible working web app.
2. **GitHub repository:** Complete source code for inspection.
3. **LinkedIn post:** Explain chosen tools and reasons, high-level architecture, prompt evolution, challenges/fixes and what GenAI handled versus what was done manually.
4. **Screen-recorded demo:** Show the deployed working application and a complete user journey.

The explainer also describes automated initial evaluation followed by manual prototype evaluation, with six automated dimensions: code quality, security, efficiency, testing, accessibility and problem alignment. It states a maximum of three submission attempts and that only the latest attempt's score counts. Confirm current rules on the official challenge portal before final submission.

---

## 17. Demo walkthrough

Recommended 2–3 minute recording:

1. Open BreatheWise AI.
2. Select an Indian city.
3. Show live air-quality values, source and timestamp.
4. Load a sample household profile.
5. Generate the morning/afternoon/evening plan.
6. Explain one indoor recommendation.
7. Show one sustainable alternative and its rationale.
8. Demonstrate the Groq/Gemini provider status only if safely exposed as non-sensitive diagnostic metadata.
9. Show a missing/stale-data state to demonstrate responsible handling.
10. End with the GitHub repository and deployed URL.

Do not show API keys, tokens, private user data or fabricated readings.

---

## 18. Definition of done

BreatheWise AI is ready for submission when:

- [ ] Multiple Indian cities can be selected.
- [ ] Real air-quality data is retrieved where available.
- [ ] AQI and pollutant measurements are correctly distinguished.
- [ ] Data source and timestamps are visible.
- [ ] Stale/missing/error states work.
- [ ] Household profiles can personalize guidance.
- [ ] Daily plan includes morning, afternoon and evening.
- [ ] Indoor guidance is included.
- [ ] Sustainable alternatives are included.
- [ ] Groq is primary and Gemini is fallback.
- [ ] AI output is schema-validated and safety-checked.
- [ ] Sample data is clearly labelled.
- [ ] Secrets are protected and RLS is configured.
- [ ] Main tests pass.
- [ ] Frontend and backend are deployed.
- [ ] GitHub repository is documented.
- [ ] LinkedIn post is published.
- [ ] Screen-recorded demo is ready.

---

## 19. Open decisions to verify during implementation

These are implementation dependencies, not assumptions:

- Confirm which CPCB data access route is technically and legally available.
- Confirm OpenAQ coverage for target Indian cities and required pollutants.
- Select currently supported Groq and Gemini model identifiers at implementation time.
- Set and document the air-data freshness threshold based on provider update cadence.
- Decide whether authentication is necessary for the evaluator demo or whether a guest/sample mode is sufficient.
- Confirm the current official PromptWars deadline, tool requirements and submission rules on the challenge portal.

**Product success criterion:** A first-time evaluator should be able to select a city, understand the actual available air-quality data, load a household profile and receive useful, explainable daily recommendations in a few minutes.
