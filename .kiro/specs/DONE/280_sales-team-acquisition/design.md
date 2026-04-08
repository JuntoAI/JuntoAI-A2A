# Design Document: Sales Team Acquisition Package

## Overview

This feature delivers four deliverables to position JuntoAI's A2A engine for sales team acquisition:

1. **4 Sales Scenario JSONs** — Drop-in `.scenario.json` files conforming to the existing `ArenaScenario` schema.
2. **Scenario Category Grouping** — A new `category` field on `ArenaScenario`, exposed via the API, and used by the frontend `ScenarioSelector` to group scenarios into `<optgroup>` sections (e.g., "Sales", "Corporate", "Everyday").
3. **`/sales` Landing Page** — A public (unauthenticated) Next.js route with sales-specific messaging, value props, scenario showcase, and CTA to the Arena.
4. **Demo Video Storyline** — A markdown shot list for a 60-second LinkedIn video featuring a sales simulation in the Glass Box view.

All four deliverables are content-heavy with minimal code. The code changes are: one optional field on the backend model, one field added to the API response, the frontend `ScenarioSelector` refactored to use `<optgroup>`, and a single Next.js page component at `frontend/app/sales/page.tsx`.

## Architecture

```mermaid
graph TD
    subgraph "Backend (no changes)"
        SR[ScenarioRegistry] -->|discovers| SD[scenarios/data/]
        SD -->|*.scenario.json| S1[saas-negotiation]
        SD --> S2[renewal-churn-save]
        SD --> S3[enterprise-multi-stakeholder]
        SD --> S4[discovery-qualification]
    end

    subgraph "Frontend"
        SP[/sales page.tsx] -->|CTA links to| AR[/arena]
        SP -->|reuses| WF[WaitlistForm]
        SP -->|uses| LI[Lucide Icons]
    end

    subgraph "Docs"
        DS[demo-storyline.md]
    end
```

The architecture is intentionally flat:

- **Backend**: One optional field added to `ArenaScenario` (`category: str`), exposed in the `list_scenarios` response. The `ScenarioRegistry._discover()` method already globs `*.scenario.json` from the data directory. Dropping files in is the entire integration.
- **Frontend**: `ScenarioSelector` refactored to group by `category` using `<optgroup>`. One new route at `frontend/app/sales/page.tsx` (server component). No new API calls, no new client state. Reuses `WaitlistForm` for lead capture.
- **Docs**: One markdown file. No tooling dependencies.

## Components and Interfaces

### Deliverable 1: Sales Scenario JSON Files

Four new files in `backend/app/scenarios/data/`:

| File | Scenario ID | Agents | Difficulty |
|---|---|---|---|
| `saas-negotiation.scenario.json` | `saas_negotiation` | Seller, Buyer, Procurement (3) | intermediate |
| `renewal-churn-save.scenario.json` | `renewal_churn_save` | CSM, Customer, Finance Compliance (3) | intermediate |
| `enterprise-multi-stakeholder.scenario.json` | `enterprise_multi_stakeholder` | Sales Director, CTO/Champion, Procurement Director, Legal/Compliance (4) | advanced |
| `discovery-qualification.scenario.json` | `discovery_qualification` | SDR, Prospect, Sales Manager/Coach (3) | beginner |

Each file conforms to the `ArenaScenario` Pydantic V2 model defined in `backend/app/scenarios/models.py`. The existing `talent-war.scenario.json` and `b2b-sales.scenario.json` serve as structural templates.

**Key design decisions for each scenario:**

**SaaS Negotiation** — Distinct from the existing `b2b_sales` scenario by focusing on SaaS-specific dynamics: annual contract value, seat-based pricing, implementation fees, and SLA penalties. The existing b2b_sales is a generic CRM deal; this one targets SaaS subscription mechanics specifically. Toggles: quota pressure (Seller), competing vendor offer (Buyer).

**Renewal / Churn Save** — Unique scenario type not covered by any existing scenario. The Customer agent starts from a position of dissatisfaction (not neutral), creating a fundamentally different negotiation dynamic. The CSM must retain rather than close. Toggles: customer already signed competitor contract (Customer), internal churn risk data (CSM).

**Enterprise Multi-Stakeholder** — The only 4-agent scenario in the sales pack. Tests the engine's N-agent capability with a champion-blocker dynamic. The CTO supports the deal but Procurement blocks on price — the Sales Director must navigate both. Toggles: CEO pre-approved budget (CTO), 20% vendor spend cut mandate (Procurement).

**Discovery / Qualification** — Non-price negotiation. Uses `value_format: "number"` and `value_label: "Qualification Score"` instead of currency. The Sales Manager/Coach agent acts as a regulator that evaluates discovery quality rather than enforcing compliance rules. Toggles: urgent internal deadline (Prospect), current vendor raised prices 40% (Prospect).

**Agent model assignments** follow the existing pattern:
- Primary negotiators: `gemini-2.5-pro` or `gemini-3-flash-preview`
- Regulators: `gemini-2.5-pro` with `fallback_model_id: "gemini-3-flash-preview"`

**Toggle design principles** (consistent with existing scenarios):
- Each toggle's `hidden_context_payload` includes behavioral instructions
- Instructions explicitly state "Do NOT reveal [the hidden information] directly"
- Toggles create asymmetric information that visibly alters negotiation dynamics

### Deliverable 2: Scenario Category Grouping

**Backend changes:**

1. **`backend/app/scenarios/models.py`** — Add optional `category` field to `ArenaScenario`:
   ```python
   category: str = Field(
       default="General",
       min_length=1,
       description="Scenario category for Arena dropdown grouping (e.g., 'Sales', 'Corporate', 'Everyday')",
   )
   ```
   Default `"General"` ensures backward compatibility — existing scenarios without the field still validate.

2. **`backend/app/scenarios/registry.py`** — Add `category` to the `list_scenarios` response dict:
   ```python
   {
       "id": s.id,
       "name": s.name,
       "description": s.description,
       "difficulty": s.difficulty,
       "category": s.category,
   }
   ```
   Sorting: primary sort by category (alphabetical, "General" last), secondary by difficulty order, tertiary by name.

3. **Existing scenario JSONs** — Add `"category"` field to all 9 existing files:
   - `talent-war`, `ma-buyout`, `b2b-sales`, `startup-pitch`, `urban-development`, `plg-vs-slg` → `"Corporate"`
   - `family-curfew`, `freelance-gig` → `"Everyday"`
   - `easter-bunny-debate` → `"Fun"`

**Frontend changes:**

4. **`frontend/lib/api.ts`** — Add `category` to `ScenarioSummary`:
   ```typescript
   export interface ScenarioSummary {
     id: string;
     name: string;
     description: string;
     difficulty: "beginner" | "intermediate" | "advanced" | "fun";
     category: string;
   }
   ```

5. **`frontend/components/arena/ScenarioSelector.tsx`** — Refactor to group by category:
   - Group `scenarios` array by `category` field
   - Render each group as an `<optgroup label="Sales">` / `<optgroup label="Corporate">` etc.
   - Within each group, keep existing `[Difficulty] Name` format
   - Sort groups alphabetically, with `"General"` last
   - Keep "My Scenarios" `<optgroup>` and "Build Your Own" at the bottom

### Deliverable 3: `/sales` Landing Page

**File**: `frontend/app/sales/page.tsx`

A server component (no `"use client"`) following the same pattern as `frontend/app/page.tsx`.

**Key differences from the main landing page:**
- No `isLocalMode` redirect — the `/sales` page renders in both cloud and local mode (Requirement 5.9)
- Sales-specific copy, not generic negotiation sandbox messaging
- Scenario showcase section highlighting the 4 sales scenarios
- CTA points to `/arena` (not waitlist-gated — users land in the Arena selector)

**Page structure:**

```
┌─────────────────────────────────────────────┐
│  Hero Section (bg-brand-offwhite)           │
│  H1: "Rehearse Your Next Deal."             │
│  Subheadline: AI deal rehearsal copy        │
│  WaitlistForm component                     │
├─────────────────────────────────────────────┤
│  Value Props (bg-brand-offwhite)            │
│  3 cards: Objection Handling, Hidden        │
│  Variables, Multi-Stakeholder Navigation    │
├─────────────────────────────────────────────┤
│  Scenario Showcase (bg-brand-gray)          │
│  4 cards: SaaS, Renewal, Enterprise,        │
│  Discovery — each with name + description   │
├─────────────────────────────────────────────┤
│  CTA Section (gradient bg)                  │
│  "Try a Sales Simulation" → /arena          │
│  Link to GitHub repo                        │
└─────────────────────────────────────────────┘
```

**Metadata export:**

```typescript
export const metadata: Metadata = {
  title: "AI Deal Rehearsal for Sales Teams",
  description: "Rehearse high-stakes sales calls with AI agents...",
  openGraph: {
    title: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    description: "...",
    url: "/sales",
    // ... standard OG fields
  },
};
```

**Component reuse:**
- `WaitlistForm` — imported directly, handles email capture + auth flow
- Lucide icons — `Target`, `Shield`, `Users`, `MessageSquare` (or similar sales-relevant icons)
- Tailwind classes — same brand palette (`brand-blue`, `brand-green`, `brand-charcoal`, `brand-offwhite`, `brand-gray`)

**No new components needed.** The page is a single server component with static content and one imported client component (`WaitlistForm`).

### Deliverable 4: Demo Video Storyline

**File**: `docs/sales-demo-storyline.md`

A markdown document with shot-by-shot direction for a 60-second video. Features the SaaS Negotiation scenario in the Glass Box view.

**Structure:**
- 5-7 shots with timestamp ranges (e.g., `0:00–0:05`)
- Each shot specifies: visual description, text overlay/caption, transition
- Demonstrates toggle activation ("one toggle changes everything")
- Ends with CTA to `/sales` landing page

**Design decision**: Feature the SaaS Negotiation scenario because it's the most universally relatable sales call type and has the clearest visual impact when toggling quota pressure.

## Data Models

One minor schema addition: an optional `category: str` field on `ArenaScenario` (default `"General"`). This is backward compatible — existing scenarios without the field pass validation unchanged.

The schema already supports everything else needed:
- `AgentDefinition` with `persona_prompt`, `goals`, `budget`, `tone`, `output_fields`, `model_id`, `example_prompt`
- `ToggleDefinition` with `hidden_context_payload` (arbitrary dict)
- `NegotiationParams` with `value_format` (supports `"number"` for the discovery scenario's qualification score) and `value_label`
- `EvaluatorConfig` (optional, can be omitted or included per scenario)
- `difficulty` field for Arena dropdown ordering

## Error Handling

Minimal error surface since this is content work:

- **Scenario JSON validation errors**: Caught by `ScenarioRegistry._discover()` which logs warnings and skips invalid files. Existing behavior, no changes needed.
- **Landing page**: Server component with no API calls — no runtime errors to handle. `WaitlistForm` has its own error handling already.
- **Missing scenario files**: The registry gracefully handles missing files. The `/sales` page hardcodes scenario descriptions (doesn't fetch them dynamically), so missing backend files don't break the page.

## Testing Strategy

### PBT Assessment

Property-based testing is **not applicable** for this feature. The deliverables are:
1. Fixed JSON content files validated by an existing Pydantic schema
2. A static landing page with no dynamic logic
3. A markdown document

There are no pure functions, no input-varying logic, no serialization/parsing, and no algorithms to test. All acceptance criteria map to example-based tests or smoke tests.

### Backend Tests (pytest)

**Scenario validation tests** — One parametrized test that loads all 4 scenario JSON files through `ArenaScenario.model_validate()`:

```python
@pytest.mark.parametrize("filename", [
    "saas-negotiation.scenario.json",
    "renewal-churn-save.scenario.json",
    "enterprise-multi-stakeholder.scenario.json",
    "discovery-qualification.scenario.json",
])
def test_sales_scenario_validates(filename):
    path = SCENARIOS_DIR / filename
    scenario = ArenaScenario.model_validate_json(path.read_text())
    assert len(scenario.agents) >= 2
    assert len(scenario.toggles) >= 2
    assert scenario.category == "Sales"
    assert any(a.type == "negotiator" for a in scenario.agents)
    assert any(a.type == "regulator" for a in scenario.agents)
```

**Structural assertions per scenario** — Verify agent counts, roles, types, max_turns ranges, toggle counts, and category values match requirements.

**Registry discovery test** — Instantiate `ScenarioRegistry`, assert all 4 new scenario IDs are present.

**Category grouping tests** — Verify `list_scenarios` response includes `category` field, verify existing scenarios have correct categories, verify sorting (categories alphabetical with "General" last).

### Frontend Tests (Vitest + RTL)

**Landing page render test** — Render `SalesPage`, assert:
- Hero section with sales-specific headline text
- At least 3 value prop cards
- At least 4 scenario showcase cards
- CTA link with `href="/arena"`
- WaitlistForm is rendered
- No redirect behavior (unlike main page)

**Metadata test** — Import the `metadata` export, assert `title` and `openGraph` fields contain sales-specific content.

**ScenarioSelector grouping test** — Render `ScenarioSelector` with scenarios that have different categories, assert:
- `<optgroup>` elements are rendered with correct labels
- Scenarios within each group retain `[Difficulty]` prefix
- "My Scenarios" and "Build Your Own" remain at the bottom
- Groups are sorted alphabetically with "General" last

### Manual Testing

- Visual review of `/sales` page at 320px, 768px, 1024px, 1920px viewports
- Verify all 4 scenarios appear in the Arena dropdown after file deployment
- Run each scenario once to confirm agents negotiate coherently
- Demo storyline reviewed by a non-technical person for clarity
