# HIKEGUARD

AI Safety Copilot for Swiss Hikers

Hackathon Product & Technical Specifications

“We don’t just show the route and the weather. We tell you whether the hike is a good idea, where the risks are, and what safer alternative to take.”

| Challenge | Hiking Safety Assistant |
| --- | --- |
| Suggested stack | RAG · MCP · AIQ |
| Primary data | MeteoSwiss Open Data · swisstopo |
| MVP target | One-day hackathon prototype |
| Version | v1.0 · 14 September 2026 |

## 1. Product Overview

HikeGuard is an AI-powered decision-support assistant for hikers in Switzerland. It combines route geometry, elevation, terrain context, weather forecasts and user context to assess hiking risk along the route — not just at the start point — and explain safer options when conditions deteriorate.

The hackathon challenge explicitly asks participants to combine Swiss hiking-route and weather information and to adapt recommendations to route-specific conditions rather than merely return weather or map information.

| Primary user | Hiker planning a trip |
| --- | --- |
| Core question | “Is this hike a good idea for me, at this time, in these conditions?” |
| Output | Segment-level risk + explanation + safer plan |
| Differentiator | Decision engine, not a weather chatbot |

## 2. Problem Statement

Current hiking tools usually separate route information from weather information. A user may see a route profile in one app and a forecast in another, but still has to make the difficult decision: “Is this route safe enough under these exact conditions?”

- Weather risk changes along the route because altitude, exposure and timing change.

- A forecast for the valley can be misleading for a ridge 1,000 m higher.

- The same route may be appropriate for an experienced adult and inappropriate for a family with children.

- Most apps inform; they do not synthesize a route-specific, time-aware safety recommendation.

## 3. Goals and Non-Goals

### 3.1 Goals

- Combine route, terrain/elevation and weather data into one assessment.

- Score risk by route segment, not only for the whole hike.

- Explain why a segment is risky using observable evidence.

- Adapt the recommendation to user context such as children, experience level or preferred risk tolerance.

- Suggest a safer departure time or alternative route when possible.

- Use transparent safety rules for critical decisions and the LLM for explanation/orchestration.

### 3.2 Non-Goals for the Hackathon MVP

- Certified mountain-safety advice or emergency dispatch.

- Complete coverage of every trail in Switzerland.

- Perfect real-time hazard detection (rockfall, avalanche, trail closure) unless data is readily available.

- A production-grade mobile app or offline navigation.

- Replacing official alerts, local authorities, rescue services or expert judgment.

## 4. Target Users and Personas

| Persona | Need | Context | What HikeGuard should do |
| --- | --- | --- | --- |
| Family hiker | Know if a route is suitable | Two children, moderate experience | Flag difficulty/weather combinations and suggest a safer option |
| Weekend hiker | Decide when to start | Known route, uncertain weather | Recommend start time and highlight critical segments |
| Tourist | Understand unfamiliar terrain | Limited local knowledge | Explain route difficulty and weather impact in plain English |
| Experienced hiker | Optimize plan | Comfortable with harder routes | Show detailed evidence, timing and segment-level hazards |

## 5. Core User Journeys

### 5.1 Pre-hike assessment

1. User selects or enters a hiking route.

1. User selects planned date/time and optional profile (experience, children, risk preference).

1. HikeGuard retrieves route/elevation and weather along the route.

1. The route is segmented and scored.

1. The assistant returns an overall decision, critical segments, reasons and recommended actions.

### 5.2 “What if?” planning

The user changes one variable — departure time, user profile or route — and HikeGuard recomputes the assessment. Example: “What if I leave at 07:00 instead of 10:00?”

### 5.3 Safer alternative

If the planned route is high risk, HikeGuard proposes a safer plan: leave earlier, take a lower-altitude alternative, shorten the route, or avoid an exposed section.

## 6. Functional Requirements

| ID | Requirement | Priority | Acceptance signal |
| --- | --- | --- | --- |
| FR-01 | User can select/input a route and planned date/time. | Must | Assessment starts with valid route/time context. |
| FR-02 | System retrieves route geometry/elevation from swisstopo or provided route data. | Must | Route profile available to scoring engine. |
| FR-03 | System retrieves weather forecast from MeteoSwiss for locations/times relevant to the route. | Must | Forecast evidence attached to route segments. |
| FR-04 | System splits route into logical segments and computes risk per segment. | Must | At least 3 segments shown with risk levels. |
| FR-05 | System returns overall risk: LOW / MODERATE / HIGH / NOT RECOMMENDED. | Must | One clear decision is displayed. |
| FR-06 | System explains top risk factors with evidence. | Must | Each high-risk segment has ≥1 explicit reason. |
| FR-07 | User context can affect scoring. | Should | Children/experience changes recommendation in demo. |
| FR-08 | System can recommend a safer departure time or alternative. | Should | At least one alternative action generated. |
| FR-09 | Chat interface can answer follow-up questions grounded in route/weather context. | Should | Follow-up answer references current hike context. |
| FR-10 | System exposes the rules/evidence behind the decision. | Should | User can see why a score was assigned. |

## 7. Data Sources & Tooling

| MeteoSwiss | Forecast / precipitation / wind / temperature / severe-weather context where available. |
| --- | --- |
| swisstopo | Route, topography, elevation and geospatial context. |
| RAG corpus | Static hiking safety guidance, trail classification, interpretation rules and product-specific knowledge. |
| MCP tools | Standardized tool interfaces used by the agent to query external data sources. |
| AIQ | Agent orchestration, planning and tool routing. |

Implementation note: for the one-day MVP, the team may use a curated route dataset or preselected demonstration routes if live integration would consume too much hackathon time. The architecture should still make the production integration path explicit.

## 8. Proposed Architecture

1. User Input — Route · date/time · profile

2. AIQ Orchestrator — Understand intent and call tools

3. Data Tools / MCP — MeteoSwiss + swisstopo

4. Route Processor — Geometry · elevation · segmentation · timing

5. Safety Rules Engine — Deterministic risk rules + weighted scoring

6. LLM / RAG Layer — Explain evidence, answer follow-ups, suggest options

7. UI — Map + risk timeline + recommendation + chat

## 9. Safety Rules Engine

Critical safety decisions should not be generated purely by an LLM. HikeGuard uses transparent rules and observable inputs for the risk decision, then uses the LLM to explain the result and coordinate tools.

| Rule example | Inputs | Decision effect | Explanation |
| --- | --- | --- | --- |
| Thunderstorm + exposed/high segment | storm probability, altitude/exposure | Increase to HIGH | “Storm risk overlaps the most exposed section.” |
| Heavy rain + difficult trail | precipitation, trail class | Increase one level | “Wet conditions may reduce grip and increase fall risk.” |
| Strong wind + ridge | wind, route exposure | Increase one level | “High wind affects balance on exposed terrain.” |
| Children + difficult trail + poor weather | profile, trail class, weather | NOT RECOMMENDED or HIGH | “Conditions are not aligned with the selected user profile.” |
| Earlier start avoids hazard window | timing, forecast evolution | Reduce risk | “Leaving 2 hours earlier avoids the forecast thunderstorm window.” |

## 10. Risk Scoring Concept

For the MVP, use a simple interpretable weighted score rather than a machine-learned safety model. Example inputs: weather severity, terrain difficulty, exposure, elevation, time-to-hazard and user-profile mismatch.

| 0–29 | LOW — conditions appear suitable for the selected profile. |
| --- | --- |
| 30–54 | MODERATE — proceed with caution; one or more manageable concerns. |
| 55–74 | HIGH — significant concerns; change timing/route or reconsider. |
| 75–100 | NOT RECOMMENDED — strong combination of hazards or profile mismatch. |

The exact thresholds are hackathon design choices, not validated safety standards. The UI should communicate that clearly.

## 11. UX / Screen Specifications

### Screen A — Plan

- Route search / route selector

- Date and departure time

- Profile: experience level, children yes/no, risk preference

- Primary CTA: Assess this hike

### Screen B — Assessment

- Overall risk badge

- Map with route segments coloured by risk

- Elevation/timeline strip

- Top 3 risk factors

- Recommended action

- “Why?” expandable evidence panel

### Screen C — Alternatives

- Leave earlier

- Lower/shorter alternative route

- Compare original vs safer option

- Change user profile and recompute

### Screen D — Chat

- “What if I leave at 7am?”

- “Why is kilometre 6 risky?”

- “Is this okay with two children?”

- “Give me the safer option.”

## 12. One-Day Hackathon MVP Scope

The MVP should optimize for a compelling end-to-end demo, not exhaustive coverage.

- 1–2 preselected Swiss routes with reliable route/elevation data.

- Weather integration for the demo route(s), live if feasible, otherwise a clearly labelled cached/fixture response.

- 3–8 route segments with calculated risk.

- At least 4 transparent safety rules.

- One profile variable that changes the result (e.g., children).

- One “what if” scenario changing departure time.

- One safer recommendation or alternative route.

- Simple visual UI: route + risk timeline + explanation.

## 13. Stretch Goals

- Dynamic alternative-route generation.

- Real-time weather refresh while hiking.

- Official warnings / trail closure ingestion.

- Multilingual support.

- Voice interaction.

- Personalized calibration based on hiker experience and equipment.

- Offline route pack / mobile mode.

- Continuous re-scoring as the hiker progresses.

## 14. Acceptance Criteria

| ID | Criterion |
| --- | --- |
| AC-01 | Given a demo route and departure time, the system produces an assessment in <10 seconds after data retrieval. |
| AC-02 | The assessment includes an overall risk and segment-level risks. |
| AC-03 | Every HIGH/NOT RECOMMENDED result displays at least one supporting weather/terrain factor. |
| AC-04 | Changing the departure time can change the recommendation when the weather timeline changes. |
| AC-05 | Changing the profile can change the recommendation in at least one demo case. |
| AC-06 | The system can explain “why” without inventing unsupported route or weather facts. |
| AC-07 | The demo visibly uses at least one of the suggested challenge technologies (AIQ / MCP / RAG), ideally two or more. |

## 15. Demo Script (2–3 minutes)

1. Select a hike planned for tomorrow at 10:00 with “family with children”.

2. Show the route and elevation profile.

3. Run assessment. HikeGuard highlights an exposed/high segment overlapping a forecast hazard window.

4. Display: HIGH RISK, with a plain-English explanation and evidence.

5. Ask: “What if we leave at 07:00?”

6. Recompute and show a lower risk because the critical segment is crossed before the hazard window.

7. Optionally show a lower/shorter route as a safer alternative.

8. Close with the message: “We turn disconnected route and weather data into a route-specific decision.”

## 16. Suggested Team Split & Implementation Plan

| Workstream | Owner profile | Deliverable |
| --- | --- | --- |
| Data / tools | Backend / geospatial | swisstopo + MeteoSwiss adapters, route segmentation |
| Agent / AIQ | AI engineer | tool orchestration, RAG, grounded explanations |
| Safety engine | Backend / product | rules, risk score, evidence object |
| Frontend | Full-stack / UX | map, timeline, badges, demo flow |
| Product / pitch | Product lead | scope, demo narrative, acceptance tests |

### Recommended build order

1. Agree on one demo route and one “bad weather” scenario.

1. Make route + weather data available in a common JSON schema.

1. Implement rules engine and generate segment risk objects.

1. Render assessment in a simple UI.

1. Add AIQ/MCP/RAG integration and grounded explanation.

1. Implement one “what-if” recomputation.

1. Polish demo and prepare fallback fixtures.

## 17. Suggested Data Contract

A common internal schema will keep the frontend, rules engine and agent decoupled.

```text
HikeAssessmentInput
- route_id / route_geometry
- planned_start_time
- user_profile { experience, children, risk_preference }

RouteSegment
- id
- geometry
- distance_km
- elevation_start / elevation_end / max_elevation
- slope / trail_difficulty / exposure (if available)
- estimated_start_time / estimated_end_time
- weather { temperature, precipitation, wind, storm_risk }

RiskAssessment
- overall_risk
- overall_score
- segments[] { risk_level, score, reasons[], evidence[] }
- recommendations[]
- safer_alternatives[]
```

## 18. Product & Technical Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Data integration takes too long | No end-to-end demo | Use one route + cached fixture as fallback. |
| LLM invents hazards | Trust problem | Risk decision comes from structured evidence/rules; LLM explains only. |
| Route/weather time alignment is wrong | Bad recommendation | Estimate segment arrival times from route duration and planned start. |
| Alternative routing is too complex | Feature incomplete | Recommend earlier start as primary fallback; alternative route is stretch. |
| Safety claim sounds authoritative | Liability / credibility | Position as decision support, show evidence and official-source links, display disclaimer. |

## 19. Hackathon Success Metrics

- A judge understands the value proposition in under 20 seconds.

- The same route produces different recommendations when timing/profile changes.

- The demo identifies at least one risky segment using combined route + weather evidence.

- The recommendation is explainable and grounded.

- The system visibly demonstrates agent/tool orchestration rather than a static mockup.

- The demo completes reliably in under 3 minutes.

## 20. Final Pitch

“Most hiking apps show the route and weather separately. HikeGuard combines terrain, timing, weather and user context to assess risk along every section of a hike, explain what matters, and recommend a safer plan or alternative route.”

Source context: Swiss AI Weeks / HPE-NVIDIA “Hiking Safety Assistant” challenge. Suggested technologies: RAG, MCP and AIQ. Public data sources: MeteoSwiss Open Data and swisstopo.
