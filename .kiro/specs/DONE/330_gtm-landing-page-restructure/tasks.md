# Implementation Plan: GTM Landing Page Restructure

## Overview

Restructure frontend landing pages to align with B2B sales GTM strategy. Homepage becomes sales-focused, new `/open-source` page for developers, `/sales` route deleted. Frontend-only — no backend changes.

## Tasks

- [x] 1. Rewrite homepage as sales-focused landing page
  - [x] 1.1 Rewrite `frontend/app/page.tsx` with sales-focused content
    - Replace hero: "Rehearse Your Next Deal. Close with Confidence." heading, subheadline about AI agents that push back/stall/negotiate, secondary paragraph about hidden variables
    - Remove "AI Negotiation Sandbox" and "Find the Win-Win" text
    - Remove ScenarioBanner import and usage
    - Add "Try a Free Simulation" CTA button linking to `/arena` in hero section
    - Keep WaitlistForm in hero as auth gate
    - Add pain/ROI section: "Your reps forget training in 2 weeks. They need practice, not more slides."
    - Add 3 sales value prop cards: Objection Handling (Shield icon), Hidden Variables (Target icon), Multi-Stakeholder Navigation (Users icon) — reuse pattern from current `/sales`
    - Add 4 scenario showcase cards: SaaS Contract Negotiation, Renewal/Churn Save, Enterprise Multi-Stakeholder, Discovery/Qualification — reuse from current `/sales`
    - Add Glass Box coaching section explaining manager coaching via replay
    - Add demo video placeholder container with play icon and "Demo coming soon"
    - Add pricing signal: "Starting at $500/month for teams"
    - Add "Supported By" section with Enterprise Ireland logo/name (subtle trust bar)
    - Add bottom CTA section: "Try a Free Simulation" → `/arena`
    - Preserve `isLocalMode` redirect to `/arena`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 8.1, 8.2, 8.3, 9.1, 9.2, 19.1_

  - [x] 1.2 Update homepage SEO metadata and JSON-LD in `frontend/app/page.tsx`
    - Export `metadata` with sales-focused title ("AI Deal Rehearsal for Sales Teams | JuntoAI"), description, OG tags, canonical "/"
    - Add JSON-LD structured data with `applicationCategory` targeting sales training, keywords for "sales rehearsal", "deal practice", "AI sales training"
    - _Requirements: 10.1, 10.2, 10.6_

  - [x] 1.3 Update root layout metadata in `frontend/app/layout.tsx`
    - Change `title.default` from "JuntoAI | AI Agent Negotiation Sandbox | A2A Protocol" to sales-focused text
    - Change `description` to reference sales deal rehearsal
    - Update `keywords` array to include "sales training", "deal rehearsal", "objection handling", "sales enablement"
    - Update `openGraph` title and description to sales messaging
    - Update `twitter` title and description to sales messaging
    - _Requirements: 10.3, 10.4, 10.5_

- [x] 2. Create open-source community page
  - [x] 2.1 Create `frontend/app/open-source/page.tsx`
    - Hero section: "AI Negotiation Sandbox. Find the Win-Win." heading (from current homepage)
    - Render ScenarioBanner component
    - 3 developer value prop cards: Not Zero-Sum (Handshake), Glass Box Reasoning (Eye), One Toggle Changes Everything (SlidersHorizontal) — move from current homepage
    - "Built in Public. Join the Community." GitHub CTA section with link to repo
    - Add clone/run instructions or link (e.g., "Clone the repo, run `docker compose up`, full stack on localhost")
    - Do NOT render WaitlistForm
    - Export `metadata` with developer-focused title/description, canonical "/open-source"
    - Add `isLocalMode` redirect to `/arena`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 19.2_

- [x] 3. Update navigation and sitemap
  - [x] 3.1 Update `frontend/components/Header.tsx`
    - Expand `showNavLinks` condition: `pathname === "/" || pathname === "/open-source"` (currently only `pathname === "/"`)
    - Add "Open Source" nav link pointing to `/open-source` in both desktop and mobile nav sections
    - Keep existing JuntoAI external link and GitHub external link
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [x] 3.2 Update `frontend/components/Footer.tsx`
    - Add "Open Source" link with `href="/open-source"` adjacent to "Release Notes" link, same styling
    - _Requirements: 14.1, 14.2_

  - [x] 3.3 Update `frontend/app/sitemap.ts`
    - Replace `/sales` entry with `/open-source` entry (priority 0.8, changeFrequency "monthly")
    - Keep `/` and `/release-notes` entries unchanged
    - _Requirements: 15.1, 15.2, 15.3_

- [x] 4. Delete sales route and clean up
  - [x] 4.1 Delete `frontend/app/sales/page.tsx` and `frontend/app/sales/` directory
    - _Requirements: 12.1, 12.2_

  - [x] 4.2 Delete `frontend/__tests__/pages/sales.test.tsx`
    - _Requirements: 18.1_

  - [x] 4.3 Update or delete `frontend/__tests__/components/GitHubCTA.test.tsx`
    - Update import to reference `/open-source` page instead of homepage, or delete if the CTA is inline in the open-source page
    - _Requirements: 18.2_

- [x] 5. Rewrite and add tests
  - [x] 5.1 Rewrite `frontend/__tests__/pages/page.test.tsx` for sales-focused homepage
    - Verify sales hero heading ("Rehearse Your Next Deal", "Close with Confidence")
    - Verify 4 scenario showcase cards are rendered
    - Verify 3 sales value prop cards (Objection Handling, Hidden Variables, Multi-Stakeholder Navigation)
    - Verify pricing signal text "Starting at $500/month for teams"
    - Verify "Supported By" section is rendered
    - Verify demo video placeholder is rendered
    - Verify "Try a Free Simulation" CTA link to `/arena`
    - Verify WaitlistForm is rendered
    - Verify old developer content is NOT present ("AI Negotiation Sandbox", "Built in Public")
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [x] 5.2 Create `frontend/__tests__/pages/open-source.test.tsx`
    - Verify developer hero heading ("AI Negotiation Sandbox")
    - Verify ScenarioBanner is rendered
    - Verify 3 developer value prop cards (Not Zero-Sum, Glass Box Reasoning, One Toggle Changes Everything)
    - Verify GitHub CTA section with correct repo link
    - Verify WaitlistForm is NOT rendered
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Run `npx vitest run` in frontend and verify all tests pass
  - Verify `/sales` returns 404
  - Verify `/open-source` renders correctly
  - Verify `/` renders sales-focused content

## Notes

- This is a frontend-only change — no backend modifications
- The Enterprise Ireland logo needs to be added to `frontend/public/` (PNG or SVG)
- The demo video placeholder is intentionally empty — the actual video will be added later per the GTM 60-day action plan
- The pricing signal ($500/month) comes directly from the GTM strategy document's pricing table
- All existing Tailwind patterns and component styles should be preserved for consistency
