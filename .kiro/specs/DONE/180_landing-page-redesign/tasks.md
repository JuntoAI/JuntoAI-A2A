# Tasks — Landing Page Redesign

## Task 1: Create shared Header component

- [x] 1.1 Create `frontend/components/Header.tsx` as a client component that reads auth state from `useSession()`
- [x] 1.2 Render the logo (`a2a-logo-400x200.png`) in the top-left using `next/image` with height 36px, wrapped in a `Link` to `/`
- [x] 1.3 Add navigation links to JuntoAI homepage (`https://juntoai.org`) and GitHub repo (`https://github.com/JuntoAI/JuntoAI-A2A`)
- [x] 1.4 Render unauthenticated state: "Join Waitlist" CTA button (links to `#waitlist` or scrolls to form)
- [x] 1.5 Render authenticated state: user email, `TokenDisplay` component, and logout button in the top-right area
- [x] 1.6 Apply `sticky top-0 z-50` positioning with brand-offwhite background and bottom border
- [x] 1.7 Add responsive compact layout for viewports below 768px using Tailwind `md:` prefixes

## Task 2: Integrate Header into root layout and simplify protected layout

- [x] 2.1 Import and render `Header` in `frontend/app/layout.tsx` above the `{children}` slot
- [x] 2.2 Remove the inline header bar (email, TokenDisplay, logout button) from `frontend/app/(protected)/layout.tsx`
- [x] 2.3 Keep the auth-guard redirect logic in the protected layout — only remove the header UI elements

## Task 3: Redesign landing page layout and hero section

- [x] 3.1 Restructure `frontend/app/page.tsx` with a centered `max-w-[1200px]` main container
- [x] 3.2 Reorder sections: Hero (headline + subheadline + WaitlistForm) → ScenarioBanner → Value Props → GitHub CTA
- [x] 3.3 Add top padding to account for the sticky Header (e.g., `pt-20`)
- [x] 3.4 Ensure all color references use `brand-*` Tailwind classes or `var(--*)` CSS custom properties — no inline hex values

## Task 4: Redesign value proposition cards with Lucide icons

- [x] 4.1 Replace emoji icons with Lucide React icons (`Handshake`, `Eye`, `SlidersHorizontal` or similar)
- [x] 4.2 Style cards with brand colors: icon backgrounds using `bg-brand-blue/10` and `bg-brand-green/10`
- [x] 4.3 Apply consistent `rounded-xl`, `shadow-sm`, and padding to all three cards
- [x] 4.4 Ensure responsive grid: single column by default, `sm:grid-cols-3` for 640px+ viewports
- [x] 4.5 Verify each card has a title (max 5 words) and description (max 25 words)

## Task 5: Add GitHub community CTA section

- [x] 5.1 Add a visually distinct GitHub CTA section below the value proposition cards in `page.tsx`
- [x] 5.2 Include heading text communicating open-source nature (e.g., "Built in Public. Join the Community.")
- [x] 5.3 Add primary button linking to `https://github.com/JuntoAI/JuntoAI-A2A` with `target="_blank"` and `rel="noopener noreferrer"`
- [x] 5.4 Include GitHub icon (Lucide `Github` icon) alongside the button
- [x] 5.5 Add supporting text explaining what developers can do (clone, run locally, contribute scenarios)
- [x] 5.6 Style the section with a gradient accent border or tinted background using `var(--gradient)` to make it visually distinct

## Task 6: Ensure mobile responsiveness

- [x] 6.1 Verify landing page renders without horizontal overflow at 320px minimum width
- [x] 6.2 Confirm value proposition cards stack vertically below 640px
- [x] 6.3 Confirm Header uses compact layout below 768px
- [x] 6.4 Verify WaitlistForm input and button are fully accessible and tappable at all viewport widths
- [x] 6.5 Use only Tailwind responsive prefixes (`sm:`, `md:`, `lg:`) — no custom media queries

## Task 7: Write unit tests

- [x] 7.1 Create `frontend/__tests__/components/Header.test.tsx` — test logo rendering, nav links, auth states, positioning classes
- [x] 7.2 Create or update `frontend/__tests__/pages/page.test.tsx` — test section order, 3 value prop cards, GitHub CTA content, max-width container, brand color classes
- [x] 7.3 Update `frontend/__tests__/components/` protected layout tests if they exist — verify inline header bar is removed
