# JuntoAI A2A MVP — Styling Guide

## Stack
- **CSS Framework**: Tailwind CSS (utility-first)
- **Icons**: Lucide React
- **Font**: Inter (system font fallback stack)

## Brand Colors
- **Primary Blue**: `#007BFF` — CTAs, links, primary actions
- **Secondary Green**: `#00E676` — AI indicators, success states
- **Dark Charcoal**: `#1C1C1E` — Text, dark backgrounds
- **Light Gray**: `#F4F4F6` — Backgrounds, borders
- **Off-White**: `#FAFAFA` — Page backgrounds

## Key UI Patterns

### Glass Box Simulation
- **Terminal Panel** (left): Dark background (`#1C1C1E`), monospace font, green/white text — machine "thinking" aesthetic
- **Chat Panel** (center): Clean chat bubbles, distinct colors per agent, iMessage-style
- **Metrics Dashboard** (top): Current offer, regulator traffic light (green/yellow/red), turn counter, token balance

### Landing Page
- High-conversion layout: headline → subheadline → email form → CTA
- Responsive: 320px to 1920px

### Responsive Breakpoints
- Mobile-first approach
- `< 1024px`: Single column (stacked panels)
- `≥ 1024px`: Side-by-side panels

## Conventions
- Use Tailwind utility classes for all layout, spacing, typography, and colors
- Custom CSS only for animations, pseudo-elements, or complex multi-state components
- Maintain 4.5:1 contrast ratio for text (WCAG AA)
- Dark mode support via `dark:` prefix classes
