# Hiking safety assistant

**Live demo:** <https://hiking-safety-assistant.vercel.app>

A mobile-first React web app (Vite, TypeScript, Tailwind v4) built from the UI spec in [docs/design/](docs/design/hiking-safety-assistant-spec.html). It currently runs on mock data for the Oeschinensee → Blüemlisalphütte route, in English and French.

### Run locally

```bash
pnpm install
pnpm dev      # http://localhost:5173
pnpm test     # unit tests
pnpm build    # production build in dist/
```

Switch between demo states (assessed, partially assessed, not assessable, stale forecast) in Settings, or with `?outcome=partial`, `?outcome=not_assessable` or `?stale=1` on `/assessment`.

### Deploy

The project is hosted on Vercel and deployed manually with the Vercel CLI (pushes to GitHub do not deploy):

```bash
vercel deploy          # preview URL
vercel deploy --prod   # updates the live demo
```

---

### Original
- **Description:** Leverage public swiss data on weather and hiking routes to create an assistant.
- **Tools:** RAG, MCP, AIQ
- **Difficulty:** Hard
- **Data:** Open Data (OGD) - MeteoSwiss and https://www.swisstopo.admin.ch/en
- **GitHub:** https://github.com/Swiss-ai-Weeks/hiking-safety-assistant

---

### Summary
Can AI help people make better decisions in the mountains? Build an assistant that combines information about Swiss hiking routes, terrain, and weather to help users understand the conditions of a planned hike. The challenge is deliberately open: your assistant might answer questions before a hike, provide context during a route, identify potential risks, or suggest alternatives. The key is to combine different sources of information into useful, context-aware guidance.

### Detailed
Build an AI assistant that combines Swiss hiking-route and weather information to help users assess and understand hiking conditions. A user might ask about a planned route, current or forecast conditions, potential risks, or whether alternative routes could be more appropriate. Solutions should combine information from multiple sources and ideally be capable of adapting recommendations to the specific route and conditions rather than simply returning weather or map information. Relevant public data is available from MeteoSwiss Open Data and swisstopo.

Participants can explore RAG, MCP, agentic workflows, geospatial reasoning, or combinations of these approaches. Suggested technologies include RAG, MCP, and AIQ.