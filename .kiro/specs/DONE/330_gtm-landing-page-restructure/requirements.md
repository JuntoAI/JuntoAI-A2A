# Requirements Document

## Introduction

Restructure the JuntoAI A2A landing pages to align with the GTM strategy document (`docs/gtm-strategy-sales-icp.md`). The primary ICP is mid-market SaaS sales leaders (VPs of Sales, Sales Enablement, Revenue Ops), not developers. The current homepage speaks to developers/open-source community, but the buyer is a VP of Sales. Open source is the distribution channel, not the product.

This restructure moves sales-focused content to `/` (homepage), creates a new `/open-source` page for the developer community, deletes the `/sales` route, and updates navigation, SEO metadata, and tests accordingly.

## Glossary

- **Homepage**: The root route (`/`) of the JuntoAI A2A frontend application
- **Open_Source_Page**: The new `/open-source` route serving developer/community content
- **Sales_Page**: The current `/sales` route (to be deleted; content merged into Homepage)
- **Header**: The sticky top navigation component (`Header.tsx`) rendered on all pages
- **Footer**: The bottom navigation component (`Footer.tsx`) rendered on all pages
- **Sitemap_Generator**: The Next.js `sitemap.ts` file that produces `sitemap.xml`
- **Root_Layout**: The Next.js root `layout.tsx` that defines default SEO metadata for the application
- **WaitlistForm**: The email/password login form component used for lead capture
- **ScenarioBanner**: The horizontally scrolling ticker component displaying negotiation scenario prompts
- **JSON_LD**: The structured data script embedded in a page for search engine consumption
- **ICP**: Ideal Customer Profile — mid-market SaaS sales leaders per the GTM strategy
- **Glass_Box**: The transparent AI reasoning display that shows agent inner thoughts before public messages
- **Value_Prop_Card**: A UI card component displaying an icon, title, and description for a product benefit

## Requirements

### Requirement 1: Sales-Focused Homepage Hero

**User Story:** As a VP of Sales visiting the homepage, I want to immediately see messaging about deal rehearsal and closing confidence, so that I understand this product solves my team's practice problem.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a hero heading containing the text "Rehearse Your Next Deal" and "Close with Confidence"
2. WHEN a visitor loads the Homepage, THE Homepage SHALL display a subheadline describing AI agents that push back, stall, and negotiate like real buyers
3. WHEN a visitor loads the Homepage, THE Homepage SHALL display a secondary paragraph referencing hidden variables and deal dynamics
4. THE Homepage SHALL NOT display the previous developer-focused heading "AI Negotiation Sandbox" or "Find the Win-Win"

### Requirement 2: Homepage Pain/ROI Section

**User Story:** As a sales leader, I want to see messaging that addresses my specific pain point (reps forgetting training), so that I feel understood and see the product as a solution.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a pain-point section containing text about reps forgetting training within 2 weeks and needing practice instead of slides
2. THE Homepage SHALL display the pain-point section between the hero section and the scenario showcase section

### Requirement 3: Glass Box Coaching Section

**User Story:** As a sales manager, I want to understand how Glass Box replay enables coaching conversations, so that I see value beyond just rep practice.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a coaching section explaining how managers use Glass Box replay to coach reps on their conversations
2. THE Homepage coaching section SHALL reference the ability to see AI buyer reasoning as a coaching conversation starter

### Requirement 4: Sales Scenario Showcase

**User Story:** As a sales leader, I want to see the specific sales scenarios available, so that I can evaluate whether the product covers my team's deal types.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display exactly 4 scenario showcase cards
2. THE Homepage scenario cards SHALL include: SaaS Contract Negotiation, Renewal/Churn Save, Enterprise Multi-Stakeholder, and Discovery/Qualification
3. WHEN a visitor loads the Homepage, each scenario card SHALL display a title, description, and difficulty level

### Requirement 5: Sales Value Propositions

**User Story:** As a sales leader, I want to see value propositions relevant to my team's challenges, so that I understand the product's differentiation.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display exactly 3 value proposition cards
2. THE Homepage value proposition cards SHALL include: Objection Handling, Hidden Variables, and Multi-Stakeholder Navigation
3. THE Homepage SHALL NOT display the previous developer-focused value propositions ("Not Zero-Sum", "Glass Box Reasoning", "One Toggle Changes Everything")

### Requirement 6: Homepage CTA — Product-Led Growth

**User Story:** As a VP of Sales visiting the homepage, I want a clear call-to-action that gets me into the product immediately, so that I can experience the value firsthand before committing.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a primary CTA button with text "Try a Free Simulation" in the hero section that links to `/arena`
2. THE Homepage hero section SHALL retain the WaitlistForm component for email capture as the authentication gate to access the arena
3. THE Homepage SHALL display a secondary CTA section at the bottom of the page with a "Try a Free Simulation" link to `/arena`
4. THE Homepage SHALL NOT display "Book a Demo" or "Schedule a Call" CTAs

### Requirement 7: Pricing Signal

**User Story:** As a VP of Sales, I want to see a pricing indication, so that I can quickly assess whether this product fits my budget before engaging further.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a pricing signal containing the text "Starting at $500/month for teams"
2. THE Homepage pricing signal SHALL appear in a visible section, not hidden in fine print

### Requirement 8: Supported By Section

**User Story:** As a VP of Sales, I want to see credible institutional backing, so that I feel confident this is a legitimate product worth evaluating.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a "Supported By" section showing the Enterprise Ireland logo and name
2. THE Homepage "Supported By" section SHALL follow the pattern used on `echo.juntoai.org` — a subtle, trust-building bar rather than a prominent marketing block
3. THE Homepage "Supported By" section SHALL appear between the value propositions and the bottom CTA section

### Requirement 9: Demo Video Placeholder

**User Story:** As a VP of Sales, I want to see a product demo video, so that I can quickly understand the product without scheduling a call.

#### Acceptance Criteria

1. WHEN a visitor loads the Homepage, THE Homepage SHALL display a demo video embed placeholder section
2. THE Homepage demo video placeholder SHALL include a visible container indicating where the video will be embedded

### Requirement 10: Homepage SEO and Structured Data

**User Story:** As a marketing team member, I want the homepage to target sales training keywords in SEO metadata and structured data, so that sales leaders find us through search.

#### Acceptance Criteria

1. THE Homepage SHALL include JSON-LD structured data with `applicationCategory` targeting sales training
2. THE Homepage JSON-LD SHALL include keywords related to "sales rehearsal", "deal practice", and "AI sales training"
3. THE Root_Layout default metadata title SHALL contain sales-focused text instead of the current "AI Agent Negotiation Sandbox" text
4. THE Root_Layout default metadata description SHALL reference sales deal rehearsal and AI sales training
5. THE Root_Layout metadata keywords SHALL include sales-specific terms such as "sales training", "deal rehearsal", "objection handling", and "sales enablement"
6. THE Homepage metadata SHALL set `alternates.canonical` to "/"

### Requirement 11: Open Source Page — Developer Content

**User Story:** As a developer, I want a dedicated page with open-source messaging and community CTAs, so that I can find the repo and run the product locally.

#### Acceptance Criteria

1. WHEN a visitor loads the Open_Source_Page, THE Open_Source_Page SHALL display a hero heading containing "AI Negotiation Sandbox" messaging
2. WHEN a visitor loads the Open_Source_Page, THE Open_Source_Page SHALL display the 3 developer-focused value proposition cards: "Not Zero-Sum", "Glass Box Reasoning", and "One Toggle Changes Everything"
3. WHEN a visitor loads the Open_Source_Page, THE Open_Source_Page SHALL render the ScenarioBanner component
4. WHEN a visitor loads the Open_Source_Page, THE Open_Source_Page SHALL display a "Built in Public. Join the Community." CTA section with a link to the GitHub repository
5. WHEN a visitor loads the Open_Source_Page, THE Open_Source_Page SHALL include instructions or a link to clone and run the project locally
6. THE Open_Source_Page SHALL NOT render the WaitlistForm component
7. THE Open_Source_Page SHALL include SEO metadata with title and description targeting open-source and developer audiences
8. THE Open_Source_Page metadata SHALL set `alternates.canonical` to "/open-source"

### Requirement 12: Delete Sales Route

**User Story:** As a developer maintaining the codebase, I want the `/sales` route removed, so that there is no duplicate or stale content.

#### Acceptance Criteria

1. THE application SHALL NOT serve any content at the `/sales` route
2. THE `frontend/app/sales/` directory SHALL be deleted from the codebase

### Requirement 13: Header Navigation Updates

**User Story:** As a visitor on any landing page, I want navigation links visible in the header, so that I can navigate between the homepage and open-source page.

#### Acceptance Criteria

1. WHEN a visitor is on the Homepage or the Open_Source_Page, THE Header SHALL display navigation links (the `showNavLinks` behavior)
2. THE Header SHALL include an "Open Source" navigation link pointing to `/open-source`
3. THE Header "Open Source" link SHALL replace or supplement the existing GitHub-only external link
4. THE Header navigation links SHALL be visible on both desktop and mobile viewports

### Requirement 14: Footer Navigation Updates

**User Story:** As a visitor, I want an "Open Source" link in the footer, so that I can discover the developer page from any page on the site.

#### Acceptance Criteria

1. THE Footer SHALL include an "Open Source" link with `href="/open-source"`
2. THE Footer "Open Source" link SHALL appear adjacent to the existing "Release Notes" link

### Requirement 15: Sitemap Updates

**User Story:** As a search engine crawler, I want the sitemap to reflect the current route structure, so that all live pages are indexed and deleted pages are not.

#### Acceptance Criteria

1. THE Sitemap_Generator SHALL include an entry for `/open-source` with `changeFrequency` of "monthly" and `priority` of 0.8
2. THE Sitemap_Generator SHALL NOT include an entry for `/sales`
3. THE Sitemap_Generator SHALL retain the existing entries for `/` and `/release-notes`

### Requirement 16: Homepage Test Coverage

**User Story:** As a developer, I want the homepage tests to validate the new sales-focused content, so that regressions are caught.

#### Acceptance Criteria

1. THE homepage test file (`frontend/__tests__/pages/page.test.tsx`) SHALL be rewritten to validate the sales-focused hero heading
2. THE homepage tests SHALL verify the presence of 4 scenario showcase cards
3. THE homepage tests SHALL verify the presence of 3 sales value proposition cards (Objection Handling, Hidden Variables, Multi-Stakeholder Navigation)
4. THE homepage tests SHALL verify the pricing signal text is rendered
5. THE homepage tests SHALL verify the social proof section is rendered
6. THE homepage tests SHALL verify the demo video placeholder is rendered

### Requirement 17: Open Source Page Test Coverage

**User Story:** As a developer, I want tests for the new open-source page, so that its content and structure are validated.

#### Acceptance Criteria

1. A new test file SHALL exist at `frontend/__tests__/pages/open-source.test.tsx`
2. THE open-source page tests SHALL verify the developer-focused hero heading is rendered
3. THE open-source page tests SHALL verify the ScenarioBanner component is rendered
4. THE open-source page tests SHALL verify the 3 developer value proposition cards are rendered
5. THE open-source page tests SHALL verify the GitHub CTA section is rendered
6. THE open-source page tests SHALL verify the WaitlistForm is NOT rendered

### Requirement 18: Sales Page Test Cleanup

**User Story:** As a developer, I want stale test files removed, so that the test suite stays clean and accurate.

#### Acceptance Criteria

1. THE sales page test file (`frontend/__tests__/pages/sales.test.tsx`) SHALL be deleted from the codebase
2. THE GitHubCTA test file (`frontend/__tests__/components/GitHubCTA.test.tsx`) SHALL be updated to import from the Open_Source_Page instead of the Homepage, or deleted if the CTA is no longer a standalone component

### Requirement 19: Local Mode Redirect Preservation

**User Story:** As a developer running in local mode, I want the homepage to still redirect to `/arena`, so that the local development experience is unchanged.

#### Acceptance Criteria

1. WHILE the application is running in local mode (`isLocalMode` is true), THE Homepage SHALL redirect the visitor to `/arena`
2. WHILE the application is running in local mode, THE Open_Source_Page SHALL redirect the visitor to `/arena`
