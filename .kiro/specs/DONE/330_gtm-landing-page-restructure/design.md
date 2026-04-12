# Design Document: GTM Landing Page Restructure

## Overview

Restructure the frontend landing pages to align with the B2B sales GTM strategy. The homepage (`/`) becomes sales-focused targeting VPs of Sales, a new `/open-source` page serves the developer community, and the `/sales` route is deleted. This is a frontend-only change — no backend modifications required.

## Architecture

```
frontend/app/
├── page.tsx              ← REWRITE: sales-focused homepage
├── open-source/
│   └── page.tsx          ← NEW: developer community page
├── sales/
│   └── page.tsx          ← DELETE
├── layout.tsx            ← UPDATE: SEO metadata pivot
├── sitemap.ts            ← UPDATE: swap /sales → /open-source
└── robots.ts             ← NO CHANGE

frontend/components/
├── Header.tsx            ← UPDATE: add "Open Source" nav link
├── Footer.tsx            ← UPDATE: add "Open Source" footer link
├── WaitlistForm.tsx      ← NO CHANGE (stays on homepage)
└── ScenarioBanner.tsx    ← NO CHANGE (moves to /open-source only)
```

## Components and Interfaces

### `frontend/app/page.tsx` — New Sales-Focused Homepage

Server component. Sections in order:

1. **Hero** — "Rehearse Your Next Deal. Close with Confidence." + subheadline + WaitlistForm + "Try a Free Simulation" CTA button → `/arena`
2. **Pain/ROI** — "Your reps forget training in 2 weeks" messaging
3. **Value Props** — 3 cards: Objection Handling, Hidden Variables, Multi-Stakeholder Navigation (reuse icons/pattern from current `/sales`)
4. **Scenario Showcase** — 4 cards: SaaS Negotiation, Renewal/Churn Save, Enterprise Multi-Stakeholder, Discovery/Qualification (from current `/sales`)
5. **Glass Box Coaching** — Section explaining manager coaching via Glass Box replay
6. **Demo Video Placeholder** — Empty container with play icon and "Demo coming soon" text
7. **Pricing Signal** — "Starting at $500/month for teams" in a visible callout
8. **Supported By** — Enterprise Ireland logo bar (subtle trust strip)
9. **Bottom CTA** — "Try a Free Simulation" → `/arena`

Exports `metadata` with sales-focused title, description, OG tags, and canonical `/`.
Includes JSON-LD structured data targeting sales training keywords.
Preserves `isLocalMode` redirect to `/arena`.

### `frontend/app/open-source/page.tsx` — New Developer Community Page

Server component. Sections in order:

1. **Hero** — "AI Negotiation Sandbox. Find the Win-Win." (current homepage hero text)
2. **ScenarioBanner** — The scrolling ticker component
3. **Value Props** — 3 cards: Not Zero-Sum, Glass Box Reasoning, One Toggle Changes Everything (current homepage cards)
4. **GitHub CTA** — "Built in Public. Join the Community." + GitHub link + clone instructions
5. No WaitlistForm anywhere on this page

Exports `metadata` with developer-focused title, description, and canonical `/open-source`.
Preserves `isLocalMode` redirect to `/arena`.

### `frontend/app/layout.tsx` — Root Layout Metadata Update

Update the default `metadata` export:
- `title.default`: pivot from "AI Agent Negotiation Sandbox" to sales-focused text like "JuntoAI | AI Deal Rehearsal for Sales Teams"
- `description`: pivot to sales deal rehearsal messaging
- `keywords`: add "sales training", "deal rehearsal", "objection handling", "sales enablement"
- `openGraph` title/description: pivot to sales messaging

### `frontend/components/Header.tsx` — Navigation Updates

- Expand `showNavLinks` condition: show nav links on `/` AND `/open-source` (currently only `/`)
- Add "Open Source" link pointing to `/open-source` alongside the existing JuntoAI and GitHub links
- Keep GitHub external link as well

### `frontend/components/Footer.tsx` — Footer Link Addition

- Add "Open Source" internal link (`/open-source`) adjacent to "Release Notes"

### `frontend/app/sitemap.ts` — Route Update

- Replace `/sales` entry with `/open-source` (priority 0.8, changeFrequency "monthly")

## Data Models

No new data models. This is a pure frontend content restructure.

## Error Handling

No new error states. All pages are static server components with no data fetching beyond the existing WaitlistForm client-side logic.

## Testing Strategy

### Unit Tests (Vitest + React Testing Library)

- **`frontend/__tests__/pages/page.test.tsx`** — Rewrite for sales-focused homepage: hero heading, 4 scenario cards, 3 value prop cards, pricing signal, supported-by section, demo video placeholder, CTA links, local mode redirect
- **`frontend/__tests__/pages/open-source.test.tsx`** — New: developer hero, ScenarioBanner, 3 dev value props, GitHub CTA, no WaitlistForm, local mode redirect
- **`frontend/__tests__/pages/sales.test.tsx`** — Delete
- **`frontend/__tests__/components/GitHubCTA.test.tsx`** — Update import to `/open-source` page or delete
- **`frontend/__tests__/components/Footer.test.tsx`** — May need update if "Open Source" link assertion is added
