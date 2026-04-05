# Requirements Document — Landing Page Redesign

## Introduction

The JuntoAI A2A landing page (`frontend/app/page.tsx`) needs a visual and structural redesign to align with the JuntoAI brand family (juntoai.org, echo.juntoai.org, kinetic.juntoai.org). The current page is functional but lacks brand cohesion, logo presence, a persistent navigation header, and a clear developer community call-to-action. This redesign covers the public landing page and the shared app shell (layout/header) to bring them up to the same design standard as the sibling JuntoAI products.

## Glossary

- **Landing_Page**: The public-facing root page (`/`) of the JuntoAI A2A application that displays the value proposition, waitlist form, and community CTA
- **App_Shell**: The shared layout wrapper (`layout.tsx` and protected `layout.tsx`) that provides the persistent header, footer, and navigation chrome across all pages
- **Header**: A persistent top navigation bar displayed on both the Landing_Page and authenticated app pages
- **Logo**: The JuntoAI brand image located at `public/a2a-logo-400x200.png`
- **GitHub_CTA**: A prominent call-to-action section inviting developers to join the public GitHub community
- **Brand_CSS**: The CSS custom properties and Tailwind theme tokens defined in `globals.css` and `tailwind.config.ts`, synced with juntoai.org
- **WaitlistForm**: The email capture form component that gates access to the arena
- **ScenarioBanner**: The infinite-scroll banner showing negotiation scenario examples
- **Viewport**: The visible area of the browser window on any device

## Requirements

### Requirement 1: Persistent Header with Logo

**User Story:** As a visitor, I want to see the JuntoAI logo and navigation in a persistent header, so that I always know what product I'm using and can navigate easily.

#### Acceptance Criteria

1. THE Header SHALL display the Logo (`a2a-logo-400x200.png`) in the top-left position on every page
2. THE Header SHALL remain fixed at the top of the Viewport during scrolling
3. WHEN the Viewport width is less than 768px, THE Header SHALL collapse navigation links into a mobile-friendly layout
4. THE Header SHALL include a link to the JuntoAI homepage (`https://juntoai.org`)
5. THE Header SHALL include a link to the public GitHub repository (`https://github.com/JuntoAI/JuntoAI-A2A`)
6. WHILE a user is authenticated, THE Header SHALL display the user email, token balance, and a logout button in the top-right area
7. WHILE a user is not authenticated, THE Header SHALL display a "Join Waitlist" or equivalent CTA button in the top-right area

### Requirement 2: Brand-Aligned Landing Page Layout

**User Story:** As a visitor, I want the landing page to look and feel like other JuntoAI products (echo.juntoai.org, kinetic.juntoai.org), so that I trust it's part of the same ecosystem.

#### Acceptance Criteria

1. THE Landing_Page SHALL use Brand_CSS custom properties and Tailwind theme tokens exclusively for colors, typography, and spacing
2. THE Landing_Page SHALL use the Inter font family as the primary typeface, consistent with juntoai.org
3. THE Landing_Page SHALL structure content in a single-column centered layout with a maximum content width of 1200px
4. THE Landing_Page SHALL display the hero section (headline, subheadline, WaitlistForm) as the first visible content below the Header
5. THE Landing_Page SHALL display the ScenarioBanner below the hero section
6. THE Landing_Page SHALL maintain a minimum text contrast ratio of 4.5:1 for all body text against its background (WCAG AA)

### Requirement 3: Developer Community Call-to-Action

**User Story:** As a developer visiting the landing page, I want a clear and prominent invitation to join the GitHub community, so that I know this is an open-source project I can contribute to.

#### Acceptance Criteria

1. THE Landing_Page SHALL display a dedicated GitHub_CTA section that is visually distinct from the hero and value proposition sections
2. THE GitHub_CTA SHALL include a heading that communicates the open-source nature of the project (e.g., "Built in Public. Join the Community.")
3. THE GitHub_CTA SHALL include a primary button linking to the public GitHub repository (`https://github.com/JuntoAI/JuntoAI-A2A`)
4. THE GitHub_CTA SHALL include supporting text that explains what developers can do (clone, run locally, contribute scenarios)
5. THE GitHub_CTA SHALL include the GitHub icon (SVG) alongside the button or heading for immediate visual recognition
6. WHEN a user clicks the GitHub_CTA button, THE Landing_Page SHALL open the GitHub repository in a new browser tab

### Requirement 4: Mobile-Responsive Design

**User Story:** As a mobile user, I want the landing page and app to render correctly on my device, so that I can use the product without horizontal scrolling or broken layouts.

#### Acceptance Criteria

1. THE Landing_Page SHALL render all content within the Viewport width without horizontal overflow on devices with a minimum width of 320px
2. WHEN the Viewport width is less than 640px, THE Landing_Page SHALL stack the value proposition cards vertically in a single column
3. WHEN the Viewport width is less than 768px, THE Header SHALL use a compact layout that fits within the Viewport width
4. THE WaitlistForm SHALL remain fully usable (input field and submit button accessible and tappable) on all Viewport widths from 320px to 1920px
5. THE Landing_Page SHALL use Tailwind responsive prefixes (`sm:`, `md:`, `lg:`) for all breakpoint-dependent styles instead of custom media queries

### Requirement 5: Value Proposition Section Redesign

**User Story:** As a visitor, I want to quickly understand what JuntoAI A2A does and why it matters, so that I'm motivated to try the demo or join the community.

#### Acceptance Criteria

1. THE Landing_Page SHALL display exactly three value proposition cards below the hero section
2. EACH value proposition card SHALL contain an icon, a title (maximum 5 words), and a description (maximum 25 words)
3. WHEN the Viewport width is 640px or greater, THE Landing_Page SHALL display the value proposition cards in a horizontal row
4. THE value proposition cards SHALL use Brand_CSS colors for icons and backgrounds (brand-blue, brand-green tints)
5. THE value proposition cards SHALL use consistent padding, border-radius, and shadow styling matching the design language of echo.juntoai.org and kinetic.juntoai.org

### Requirement 6: Logo in App Shell (Authenticated Pages)

**User Story:** As an authenticated user, I want to see the JuntoAI logo in the app header, so that the product feels polished and branded throughout my session.

#### Acceptance Criteria

1. THE App_Shell SHALL display the Logo in the top-left position of the Header on all authenticated pages (arena, glass box, outcome receipt)
2. WHEN a user clicks the Logo in the App_Shell, THE App_Shell SHALL navigate the user to the Landing_Page (`/`)
3. THE Logo in the App_Shell SHALL render at a height that fits within the Header without causing layout overflow (maximum 40px height)

### Requirement 7: CSS Architecture Alignment

**User Story:** As a developer maintaining this codebase, I want the landing page to use the same CSS architecture as juntoai.org, so that brand updates propagate consistently.

#### Acceptance Criteria

1. THE Landing_Page SHALL reference all brand colors through CSS custom properties defined in `globals.css` (e.g., `var(--primary-blue)`) or Tailwind theme tokens (e.g., `brand-blue`)
2. THE Landing_Page SHALL define no inline color hex values in component JSX
3. THE Brand_CSS SHALL define the gradient variable (`--gradient: linear-gradient(135deg, #007BFF 0%, #00E676 100%)`) and THE Landing_Page SHALL use this gradient for accent elements
4. IF a new color is needed, THEN THE Landing_Page SHALL add the color to both `globals.css` custom properties and `tailwind.config.ts` theme extension before referencing the color in components
