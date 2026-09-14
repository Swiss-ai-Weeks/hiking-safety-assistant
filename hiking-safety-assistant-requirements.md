# Hiking Safety Assistant — High-Level Requirements

> **Purpose:** Decision-support assistant that fuses Swiss hiking-route/terrain data with weather data into context-aware guidance for assessing hiking conditions.
>
> **Data sources:** MeteoSwiss Open Data (OGD) · swisstopo
> **Suggested tech:** RAG · MCP · agentic workflows · geospatial reasoning · AIQ
> **Reference:** https://github.com/Swiss-ai-Weeks/hiking-safety-assistant

---

## Scope & Primary User Goals

The assistant helps a user assess and understand the conditions of a Swiss hike by fusing route/terrain data with weather data into context-aware guidance. It serves three moments:

- **Pre-hike planning**
- **In-situ support during a route**
- **Risk identification with alternatives**

It is a decision-support tool, **not an authority** — this distinction drives several non-functional requirements below.

---

## Functional Requirements

### Route intelligence
- **FR-1:** Accept a hike specified by name, start/end points, a drawn or uploaded track (GPX), or a region, and resolve it to a concrete route with terrain attributes (distance, ascent/descent, difficulty grade, surface/exposure where available).
- **FR-2:** Return route characteristics relevant to safety: exposure, technical sections, hut/shelter locations, water sources, and escape/bail-out points where derivable from swisstopo data.
- **FR-3:** Support the official Swiss hiking scale (T1–T6) and surface the grade so users self-select against their ability.

### Weather & conditions
- **FR-4:** Retrieve current, forecast, and (where available) nowcast weather for the route, resolved along its geography and elevation profile rather than a single point.
- **FR-5:** Represent conditions that matter for mountain safety specifically: precipitation, temperature and freezing level, wind, visibility/cloud base, thunderstorm probability, and — as a stretch — snow/avalanche-relevant signals.
- **FR-6:** Reason about *timing* — conditions at the user's expected position at a given hour, not just conditions "today."

### Risk assessment
- **FR-7:** Combine terrain and weather to flag route-specific hazards (e.g., exposed ridge + high wind + afternoon thunderstorm window) rather than restating raw weather.
- **FR-8:** Communicate risk with clear severity and the reasoning behind it, so the user can judge it themselves.
- **FR-9:** Account for user-provided context (experience level, group, gear, planned start time) when it's offered, and degrade gracefully when it isn't.

### Recommendations & alternatives
- **FR-10:** Suggest mitigations (earlier start, turnaround time, alternative segments) and, where appropriate, alternative routes better matched to the conditions and the user's profile.
- **FR-11:** Explain *why* an alternative is proposed, tying it back to specific conditions/terrain.

### Interaction
- **FR-12:** Support natural-language Q&A across all of the above, in a conversational, multi-turn form that retains route/context within a session.
- **FR-13:** Cite or attribute the underlying data sources for any safety-relevant claim.

---

## Data & Integration Requirements

- **DR-1:** Integrate MeteoSwiss Open Data (OGD) as the weather source and swisstopo as the route/terrain/geospatial source.
- **DR-2:** Perform geospatial reasoning — spatial joins between a route geometry and weather/terrain layers, elevation-aware sampling along the track.
- **DR-3:** Handle source unavailability, staleness, and partial coverage explicitly; never silently substitute or fabricate conditions.
- **DR-4:** Record data provenance and timestamps for every fact surfaced to the user.

---

## AI / Agentic Requirements

- **AR-1:** Use RAG over the corpus that suits retrieval (route descriptions, hut info, hiking-scale definitions, safety guidance) while keeping live weather on a real-time path, not the vector store.
- **AR-2:** Expose data sources and capabilities as tools (MCP) so the assistant composes weather + terrain + reasoning rather than answering from a single lookup.
- **AR-3:** Support an agentic workflow able to decompose a query, gather from multiple sources, and synthesize — with the orchestration observable/evaluable (this is where AIQ fits: measuring correctness, groundedness, and latency of the agent).
- **AR-4:** Ground outputs in retrieved data and constrain the model against unsupported safety claims (no invented hazards, no invented conditions).

---

## Non-Functional Requirements

- **NFR-1 (Safety-criticality):** Treat guidance as decision-support. Optimize to avoid *false reassurance* — under-warning is more dangerous than over-warning in this domain.
- **NFR-2 (Reliability):** Define behavior for degraded/missing data; a stale forecast must be labeled as such.
- **NFR-3 (Groundedness):** Every safety-relevant statement traces to a retrieved source; unsupported claims are suppressed, not hedged.
- **NFR-4 (Latency):** Interactive response times for planning; the in-situ use case implies tolerance for poor/intermittent mountain connectivity.
- **NFR-5 (Localization):** Support Switzerland's language context (DE/FR/IT/EN) at least for place names and ideally the interface.
- **NFR-6 (Privacy):** Location and route data are sensitive; minimize retention and be explicit about what's stored.
- **NFR-7 (Observability):** Agent steps, tool calls, and data freshness are inspectable for evaluation and debugging.

---

## Safety, Trust & Liability (Domain-Critical)

- **SR-1:** Present a clear disclaimer that the tool supplements, and does not replace, official sources, local knowledge, and the user's own judgment.
- **SR-2:** Point users to authoritative channels (avalanche bulletins, MeteoSwiss warnings, emergency services 1414 / 112) rather than positioning itself as the final word.
- **SR-3:** Fail safe: when confidence or data quality is low, say so and advise caution rather than producing a confident answer.
- **SR-4:** Avoid definitive "safe / go" verdicts; frame outputs as conditions, risks, and considerations.

---

## Constraints & Assumptions

- Bounded to Swiss public open data (MeteoSwiss OGD, swisstopo); coverage and update cadence of those sources constrain what's answerable.
- Assumes users may have limited connectivity in the field (affects the in-situ design).
- Hackathon horizon implies a demonstrable vertical slice over full breadth — a good scoping cut is a strength.

---

## Explicitly Out of Scope (Suggested)

Live rescue / dispatch, real-time crowd/trail-traffic data, gear commerce, and non-Swiss regions — unless deliberately added later.

---

## Architectural Tensions to Resolve Early

- **RAG-vs-live-data split (AR-1):** the most consequential design decision — keep live weather off the vector store.
- **In-situ connectivity (NFR-4):** either commit to a pre-fetch/offline model or drop that moment from scope.
- **False-reassurance stance (NFR-1):** should be an explicit, agreed principle, since it trades against sounding decisive in a demo.
