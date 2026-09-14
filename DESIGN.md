# Hiking Safety Assistant — Design Conventions

**Status:** v1, derived from `Hiking Safety Assistant.dc.html` (screens 01–05).
**Audience:** Anyone adding a screen, component, or copy to the app. Read this before building anything user-facing.
**Companion docs:** `ARCHITECTURE.md` (invariants INV-1..7, KAD-8), `architecture-notes.md` (3-tap pre-flight, field mode), `hiking-safety-assistant-behavioural-analysis.md` (biases, framing).

The reference screens show the conventions applied. This file states the conventions so new screens match without copying pixels.

---

## 1. Principles → build rules

Based on the seven principles from Apple's "Design principles" session (WWDC26-250), applied to this product.

| Principle | Rule for this app |
|---|---|
| **Purpose** | Every screen answers one question, stated in its headline. If you can't name the question, don't build the screen. Assessment leads with the crux (most exposed point at the hour you're there), never the trailhead. |
| **Agency** | Defaults are pre-filled from the fused model and *confirmed*, not assembled. Any "Adjust" path is optional and never blocks the primary path. The go decision is always the hiker's; the app never says go or don't go. |
| **Forgiveness** | Everything set during planning is editable until "Start hike". Destructive or irreversible actions (End hike, delete plan) confirm once, in plain words. No other confirmation dialogs. |
| **Responsibility** | Ask for permissions only at the moment they're needed, with the reason on screen (location: at "Start hike" and "Locate me"). Name what the system cannot see. Never use the word *safe*. Emergency numbers (1414, 112) are always reachable in field mode; the app never initiates contact. |
| **Familiarity** | Back is a chevron, top-left, 40 px. One primary button per screen, bottom-anchored, plum. Numbered steps for sequences. Severity colours are amber and red only; "nothing flagged" is grey, never green or a checkmark. |
| **Flexibility** | EN/DE for all rendered sentences; place names stay in their official language. Field mode works fully offline from the downloaded pack. Layouts reflow between 360 and 430 px wide. |
| **Simplicity** | Three decisions before departure, everything else is read-only context. Plain language. Rule IDs and source timestamps live in provenance footnotes, never in body copy. |
| **Craft** | Type, colour, spacing and targets from the tokens below, without exception. Skeletons instead of spinners. 44 px minimum targets; 52 px+ in field mode. |
| **Delight** | The emotion is *steadiness*: the app already knows what you decided and reminds you calmly. No confetti, no celebratory states. Warmth comes from copy and the serif, not decoration. |

---

## 2. Tokens

All colours are OKLCH. Warm neutral hue 60–75 throughout.

### Colour

| Token | Value | Use |
|---|---|---|
| `canvas` | `oklch(0.975 0.006 75)` | Screen background |
| `card` | `#ffffff` | Cards, sheets |
| `card-border` | `oklch(0.88 0.01 75)` | 1 px card borders, secondary button outline |
| `divider` | `oklch(0.92 0.008 75)` | Hairlines inside cards |
| `surface-muted` | `oklch(0.95 0.01 75)` | Inset panels ("What we can't see", plan rows) |
| `ink` | `oklch(0.22 0.012 60)` | Primary text, crux card background, step badges |
| `ink-2` | `oklch(0.35 0.012 60)` | Body text on cards |
| `ink-3` | `oklch(0.5 0.012 60)` | Labels, captions, eyebrows |
| `ink-4` | `oklch(0.55 0.012 60)` | Provenance footnotes, disabled text |
| `action` | `oklch(0.5 0.12 300)` | Primary buttons, links, selected state, back chevron |
| `action-hover` | `oklch(0.45 0.12 300)` | |
| `severity-high` | `oklch(0.62 0.17 40)` | Red-orange: hazard at/above threshold; not-assessable dot; emergency button |
| `severity-moderate` | `oklch(0.78 0.13 70)` | Amber: hazard below threshold; partially assessed; stale forecast |
| `severity-none` | `oklch(0.8 0.02 75)` | Grey: nothing flagged. **Never green.** |
| `field-bg` | `oklch(0.17 0.01 60)` | Field mode screen background |
| `field-card` | `oklch(0.24 0.012 60)` | Field mode cards |
| `field-control` | `oklch(0.32 0.012 60)` | Field mode option rows |
| `field-text-2` | `oklch(0.85 0.01 75)` | Field mode secondary text |
| `field-text-3` | `oklch(0.7 0.02 75)` | Field mode captions |

Rules: the action colour is never used to signal safety or severity. Severity colours are never used for buttons except the field-mode Emergency button. Text on any accent or photo ground is full-opacity, contrast ≥ 4.5:1.

### Type

Fonts: **Figtree** (UI) and **Literata** (headlines, key values). Nothing else.

| Style | Font | Size / weight | Use |
|---|---|---|---|
| `display` | Literata | 30–34 / 500, line-height 1.15 | Screen headline (one per screen) |
| `title-serif` | Literata | 24–26 / 500 | Crux value, card headline, not-assessable message |
| `title` | Figtree | 16–17 / 600 | Card titles, button labels, hazard titles |
| `body` | Figtree | 14–15 / 400, line-height 1.5 | Body copy |
| `label` | Figtree | 12–13 / 400–600 | Field labels, captions |
| `eyebrow` | Figtree | 12–13 / 600, uppercase, letter-spacing 0.08em | Section markers ("Most exposed point") |
| `footnote` | Figtree | 12 / 400, `ink-4` | Provenance |
| `field-display` | Literata | 34 / 500 | Field mode headline |
| `field-body` | Figtree | 17–20 / 500–600 | Field mode rules and options |

Never below 12 px. Field mode never below 13 px, body 17 px+.

### Spacing, shape, elevation

- Spacing scale: 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24. Screen side padding 18–22 px. Card padding 16 px. Gap between cards 14 px, between sections 18 px.
- Radii: cards 16 px, large cards (crux, field) 18 px, buttons 14 px, secondary buttons and inset rows 12 px, pills 18 px (full), badges 50%.
- Elevation: none. Cards are separated by border, not shadow. The only shadow is the bottom sheet on the map (`0 -6px 20px rgba(0,0,0,0.06)`).
- Safe areas: header starts at 58 px (with back) or 66 px (headline screens); bottom action padding 16 px top, 48 px bottom.

---

## 3. Layout patterns

Every screen is a column: **header → scrolling content → bottom action**.

**Header (with back)**: 40 px chevron in `action`, then title (`title` 15/600) with one-line context under it (`label`, `ink-3`), then an optional right-side pill (36 px, outlined, `action` text) for a secondary destination such as "Map" or "Locate me". Bottom hairline `oklch(0.9 0.008 75)`.

**Header (headline screen, no back)**: eyebrow + `display` headline, e.g. "Plan a hike / Where are you going, and when?". Used for top-level entry points only.

**Content**: cards stacked with 14 px gap. Section titles are `title` 15/600 with 4 px side padding, sitting above their cards, not inside them.

**Bottom action**: one primary button, 54 px, full width, `action`. An optional secondary sits beside it (fixed width 96–120 px, outlined). Never two primaries. Never hide a disabled primary; show it in `card-border` fill with `ink-4` text.

**Bottom sheet** (map and future overlays): white, 20 px top radii, 36×4 grab handle, section title row, list rows 10 px vertical padding with hairline dividers.

**Reflow**: `max-width`, flex/grid with `gap`, no fixed heights on text boxes. Test at 360 and 430 px.

---

## 4. Components

### Card
White, 1 px `card-border`, 16 px radius, 16 px padding. Rows inside separated by `divider` hairlines. Tappable cards get a `›` chevron in `ink-4` on the right; nothing else indicates tappability.

### Outcome line
First element under the header on any assessment-derived screen. 8 px dot + bold status + `·` context in `ink-4`.
- **Assessed**: `ink` dot. "Assessed · all segments · forecast from HH:MM today"
- **Partially assessed**: `severity-moderate` dot. Segments not evaluated are listed as dashed cards under Flagged (see below); recommendations depending on them are hidden.
- **Not assessable**: `severity-high` dot. Screen shows only the reason card and official channels (see 02b). No hazards, no recommendations, no primary action.
- **Stale** (INV-4): dot turns `severity-moderate`, text reads "forecast from 06:40, 7 h old"; crux values get a "stale" pill.

### Crux card
`ink` background, white text, 18 px radius. Eyebrow "Most exposed point" → `title-serif` place + altitude → "You'd be there around **HH:MM**" → up to three value tiles (`oklch(0.3 0.012 60)` fill, 12 px radius, label 11 px + value 20/600). The one value that triggers the top hazard is coloured `oklch(0.85 0.14 70)`. Exactly one crux card per assessment.

### Timeline
Bar chart of one variable along the route, one bar per waypoint, coloured by severity for that hour. Labels: time over place name; the crux column is bold `ink`. Always includes the descent. Footnote explains the pace assumption.

### Hazard card
Card with a 10 px severity dot, then: title (place + time window), body (the rendered template sentence), optional **"Lifts if …"** line in `label` with bold lead, provenance footnote (`Rule ID vN · basis · model HH:MM`).
- No icons, no checkmarks, no green.
- **Not evaluated** variant: `surface-muted` fill, 1 px dashed `oklch(0.8 0.012 60)` border, title "Not evaluated: segment", body naming the missing input and the sentence "Not evaluated is not the same as nothing found."
- **Empty state** is a sentence, not an empty list: "Nothing flagged on X → Y given data as of HH:MM."

### "What we can't see"
`surface-muted` panel, 16 px radius. Title + dash list of specific gaps (missing feeds, missing observations, assumed inputs). Present on every assessment. Replaces boilerplate disclaimers as the primary trust device; the short INV-7 disclaimer still appears as a footnote at the end.

### Recommendation cards ("Ways to keep the day")
Mitigations first, then alternatives (ARCHITECTURE §8). The system's suggested option gets a 1.5 px `action` border and a "Suggested" tag in `action`. Body is gain-framed: what you keep, then what pushing on costs.

### Step card (pre-flight)
24 px round badge (`ink` fill, white number; `action` fill with ✓ when done), title, helper text, controls, and a result line under a divider once answered. Steps not yet reachable render at 55% opacity, never hidden.

### Choice chips
Equal-width, 46 px, 12 px radius, 1.5 px `card-border`; selected = `action` fill + white text. Used for the reference-class question. Never a slider or a self-rating scale.

### Plan row
`surface-muted`, 12 px radius, 12×14 padding. Label in `ink-3`, value in `title`. Highlighted values (turnaround time) in `action`.

### Buttons
| Kind | Height | Style |
|---|---|---|
| Primary | 54 px | `action` fill, white, 17/600, 14 px radius |
| Primary (inline, inside card) | 48 px | same, 12 px radius, 15/600 |
| Secondary | 46–54 px | 1.5 px `card-border`, `ink-2` text |
| Outline action | 46–48 px | 1.5 px `action` border, `action` text (e.g. Try again) |
| Header pill | 36 px | outline, 18 px radius, 14/600 `action` |
| Disabled | as primary | `card-border` fill, `ink-4` text |
| Emergency (field) | 54 px | `severity-high` fill, white |

Hover: `action-hover`. Active: `scale(0.98)`. Focus: 2 px `action` outline, 2 px offset.

### Field mode
Dark only. Status line (offline · plan age · clock). `field-display` headline that states position relative to the rule ("You're ahead of your turnaround."). Rule card quoting the pre-commitment verbatim. Observation card with 3 options at 52 px, caption "Optional. Skips itself in 2 minutes." Bottom: secondary action + Emergency. No live reasoning; every sentence on this screen comes from the offline pack.

### Map
Leaflet + OpenStreetMap tiles (attribution required). Route split at segment boundaries, coloured by highest severity, white casing under the coloured line. Waypoint labels: white chip, 11/600, showing place and traversal hour; crux chip in `ink`. Legend chip top-left. Segment bottom sheet; tapping a row pans the map. Tiles for the corridor are cached into the offline pack.

### Share / decision card
Photo header with dark fade from 40%, eyebrow + `title-serif` route + context line over it. Body sections with eyebrow labels: "We turn around if", "Watch for", "Not checked", then provenance footnote. Designed to be read by someone who did not plan the hike.

### Image slots
Use the project `image-slot` component for any photo area; user photos live in `uploads/`. Text over photos sits on a gradient ≥ 0.85 alpha.

---

## 5. Copy

Facts are rendered template sentences or cited excerpts (KAD-8). UI copy around them follows these rules.

- **Forbidden words**: safe, go, fine, clear to, all good, green light, verdict, guaranteed.
- **Use instead**: "nothing flagged", "given data as of HH:MM", "lifts if", "your rule says", "we can't see", "not evaluated", "not assessable".
- Name the **place, time, reason, and what would lift it** in every warning. Generic warnings are alarm fatigue.
- Frame alternatives as **gains** ("keeps your 16:10 boat"), then state the cost of continuing.
- Ask about **past outcomes**, never self-ratings ("how long did your last hike of this size actually take?").
- Second person, present tense, sentence case. Numbers with thin-space thousands (2 778 m), 24 h times, `·` as separator, `→` for route direction.
- Provenance format: `Rule WIND-EXP-02 v3 · SAC guidance · ICON-CH1 06:40`.
- German versions must exist for every string before a screen ships (per-language release gate). Place names never translated.

---

## 6. States every screen must define

Before a screen is done, specify: loading (skeleton blocks in final positions, no spinner), empty (a sentence, not a blank), degraded (which data is missing and how it's disclosed), offline (what still works from cache), error (reason + official channel + retry). Assessment-derived screens inherit the outcome-line states in §4.

---

## 7. Adding a new screen: checklist

1. What single question does it answer? Put it in the headline.
2. Which of the three selves uses it (planning / morning / field)? Pick light or field-mode treatment accordingly.
3. Header pattern, content cards, one bottom primary.
4. Which facts appear, and does each have a template + provenance?
5. What can't the system see here? Add it.
6. Define the five states in §6.
7. Copy passes the forbidden-word list; DE strings exist.
8. Targets ≥ 44 px (≥ 52 px in field mode); text ≥ 12 px; contrast ≥ 4.5:1.
9. Add the screen to `Hiking Safety Assistant.dc.html` as a numbered frame with a one-paragraph note.
