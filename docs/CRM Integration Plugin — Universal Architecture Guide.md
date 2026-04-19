# CRM Integration Plugin — Universal Architecture Guide

> **Purpose**: This document defines the CRM-side plugin architecture for integrating any CRM system (EspoCRM, HubSpot, Salesforce, Pipedrive, etc.) with the JuntoAI A2A Simulation Engine. It is CRM-agnostic by design — each CRM implementation follows the same contract.
>
> **Audience**: Plugin developers building CRM extensions that connect to the A2A Integration API.

---

## 1. Core Concept

A CRM plugin adds a "Run Simulation" capability to Contact/Deal/Lead views. The plugin:

1. Lets the user pick a simulation scenario from a list fetched from A2A
2. Auto-maps CRM entity fields to scenario context variables
3. Triggers a simulation via the A2A Integration API
4. Stores the simulation reference (session ID, status, viewer URL) on the CRM entity
5. Displays simulation status and results inline, with a link to the full Glass Box viewer

**The plugin is a thin client.** All simulation logic, AI orchestration, and result rendering happens in A2A. The CRM plugin only handles: trigger, poll, display link.

---

## 2. Plugin Capabilities (Required)

Every CRM plugin MUST implement these capabilities:

### 2.1 Configuration Panel

- **API Key input**: Admin-level setting where the A2A integration API key (`a2a_live_...`) is stored securely. Never exposed to non-admin users.
- **A2A Base URL**: Configurable endpoint (default: `https://api.juntoai.org/api/v1/integrations`). Allows pointing to self-hosted instances.
- **Connection test**: A "Test Connection" button that calls `GET /integrations/health` to verify the API key works.

### 2.2 Contact/Deal View Panel

A panel or widget added to the Contact (or Deal/Lead) detail view containing:

- **"Run Simulation" button** — opens the scenario picker modal
- **Simulation history table** — lists past simulations for this entity:
  - Scenario name
  - Status badge (Running / Completed / Failed)
  - Outcome (Agreed / Blocked / Failed) — shown when completed
  - Date/time
  - "View" link → opens Glass Box viewer URL in new tab
  - "View Summary" link → opens inline summary (if available)

### 2.3 Scenario Picker Modal

Triggered by "Run Simulation" button:

1. Fetches available scenarios from `GET /integrations/scenarios`
2. Displays scenario cards with: name, description, category, difficulty
3. Shows required context fields for the selected scenario
4. Auto-fills context from CRM entity fields (see Field Mapping below)
5. Allows manual override of any auto-filled field
6. Optional: toggle selection (fetched from scenario definition)
7. "Start Simulation" button → calls `POST /integrations/simulate`

### 2.4 Status Polling / Webhook Receiver

After triggering a simulation, the plugin must track completion:

**Option A — Polling (simpler, recommended for v1):**
- Poll `GET /integrations/sessions/{session_id}` every 10 seconds
- Stop polling when status is `completed` or `failed`
- Update the simulation record in CRM with outcome data

**Option B — Webhook (recommended for v2):**
- Register a webhook URL during simulation creation (`callback_url` field)
- Receive POST from A2A when simulation completes
- Update the simulation record in CRM with outcome data

### 2.5 Simulation Record Entity

The plugin creates a custom entity/object to store simulation references:

| Field | Type | Description |
|---|---|---|
| `id` | string | CRM-generated unique ID |
| `session_id` | string | A2A session ID |
| `contact_id` | string | FK to the CRM Contact/Deal entity |
| `scenario_id` | string | Which scenario was run |
| `scenario_name` | string | Human-readable scenario name |
| `status` | enum | `running`, `completed`, `failed` |
| `outcome` | enum | `agreed`, `blocked`, `failed`, `null` |
| `outcome_summary` | text | 1-2 sentence result summary |
| `viewer_url` | url | Link to Glass Box viewer |
| `turns_completed` | int | Number of negotiation turns |
| `created_at` | datetime | When simulation was triggered |
| `completed_at` | datetime | When simulation finished |

---

## 3. Field Mapping — CRM Entity → A2A Context

The plugin auto-maps CRM fields to A2A scenario context. This mapping is configurable per CRM but follows a universal schema.

### 3.1 Universal Context Schema

The A2A Integration API accepts a `context` object with these standard fields:

```json
{
  "contact_name": "string",
  "company": "string",
  "role": "string",
  "industry": "string",
  "deal_value": "number",
  "deal_stage": "string",
  "pain_points": ["string"],
  "competing_vendors": ["string"],
  "budget_approved": "boolean",
  "custom_fields": {
    "any_key": "any_value"
  }
}
```

### 3.2 Default Field Mappings by CRM

**EspoCRM:**
| A2A Context Field | EspoCRM Entity Field |
|---|---|
| `contact_name` | `Contact.name` |
| `company` | `Contact.account.name` |
| `role` | `Contact.title` |
| `industry` | `Account.industry` |
| `deal_value` | `Opportunity.amount` |
| `deal_stage` | `Opportunity.stage` |

**HubSpot:**
| A2A Context Field | HubSpot Property |
|---|---|
| `contact_name` | `firstname` + `lastname` |
| `company` | `company` |
| `role` | `jobtitle` |
| `industry` | `industry` |
| `deal_value` | `amount` (Deal object) |
| `deal_stage` | `dealstage` (Deal object) |

**Salesforce:**
| A2A Context Field | Salesforce Field |
|---|---|
| `contact_name` | `Contact.Name` |
| `company` | `Account.Name` |
| `role` | `Contact.Title` |
| `industry` | `Account.Industry` |
| `deal_value` | `Opportunity.Amount` |
| `deal_stage` | `Opportunity.StageName` |

### 3.3 Custom Field Mapping

Admins can configure additional field mappings in the plugin settings. Any unmapped fields can be manually entered in the scenario picker modal.

---

## 4. EspoCRM Extension — Implementation Reference

This section provides the concrete implementation guide for the EspoCRM extension. Other CRM plugins should follow the same patterns adapted to their platform.

### 4.1 Extension Structure

```
extensions/a2a-simulation/
├── app/
│   └── Espo/
│       └── Modules/
│           └── A2ASimulation/
│               ├── Controllers/
│               │   └── A2ASimulation.php        # REST controller
│               ├── Services/
│               │   └── A2ASimulation.php        # Business logic + A2A API calls
│               ├── Entities/
│               │   └── A2ASimulation.php        # Custom entity class
│               └── Resources/
│                   ├── metadata/
│                   │   ├── entityDefs/
│                   │   │   └── A2ASimulation.json   # Entity schema
│                   │   ├── clientDefs/
│                   │   │   └── Contact.json         # Adds panel to Contact view
│                   │   └── scopes/
│                   │       └── A2ASimulation.json   # Entity scope config
│                   ├── layouts/
│                   │   └── Contact/
│                   │       └── detail.json          # Panel placement
│                   └── i18n/
│                       └── en_US/
│                           └── A2ASimulation.json   # Labels
├── client/
│   └── modules/
│       └── a2a-simulation/
│           └── src/
│               ├── views/
│               │   └── contact/
│               │       └── record/
│               │           └── panels/
│               │               └── a2a-simulations.js   # Panel view
│               └── views/
│                   └── a2a-simulation/
│                       └── modals/
│                           └── run-simulation.js        # Scenario picker
├── scripts/
│   └── AfterInstall.php                                 # Post-install setup
└── manifest.json
```

### 4.2 Key Implementation Details

**Service Layer (`Services/A2ASimulation.php`):**
- All A2A API calls go through this service — never from the frontend JS directly
- API key is stored in EspoCRM's Integration entity (admin-only access)
- Uses `cURL` or Guzzle for HTTP requests to A2A
- Handles error responses gracefully (timeout, 401, 404, 500)

**Frontend Panel (`panels/a2a-simulations.js`):**
- Extends `Espo.Views.Record.Panels.Relationship`
- Shows simulation history as a list with status badges
- "Run Simulation" button triggers the modal
- Auto-refreshes when a running simulation completes (polling via `setInterval`)

**Scenario Picker Modal (`modals/run-simulation.js`):**
- Fetches scenarios from the EspoCRM backend (which proxies to A2A)
- Renders scenario cards with description and required fields
- Auto-fills context from the current Contact record
- Validates required fields before submission
- Shows loading state during simulation creation

### 4.3 Security Model

- API key stored server-side only (EspoCRM Integration settings)
- Frontend JS never sees the API key — all A2A calls proxied through EspoCRM backend
- EspoCRM's built-in ACL controls who can trigger simulations (role-based)
- Simulation records inherit Contact's access permissions

### 4.4 Installation Flow

1. Admin uploads extension ZIP via EspoCRM Admin → Extensions
2. Extension creates the `A2ASimulation` entity and adds panel to Contact view
3. Admin navigates to Admin → Integrations → A2A Simulation
4. Admin enters API key and A2A base URL
5. Admin clicks "Test Connection" to verify
6. Users with appropriate role permissions see the panel on Contact views

---

## 5. UI/UX Specifications

### 5.1 Contact View Panel

```
┌─────────────────────────────────────────────────┐
│ A2A Simulations                    [Run Simulation] │
├─────────────────────────────────────────────────┤
│                                                     │
│  Investor Pitch  ●  Completed — Agreed              │
│  Apr 19, 2026    6 turns    [View Results]          │
│                                                     │
│  First Sales Call  ◐  Running...                    │
│  Apr 19, 2026      [View Live]                      │
│                                                     │
│  M&A Buyout  ●  Completed — Blocked                 │
│  Apr 18, 2026    4 turns    [View Results]          │
│                                                     │
└─────────────────────────────────────────────────┘
```

**Status badges:**
- 🟢 `Completed — Agreed` (green)
- 🔴 `Completed — Blocked` (red)
- 🟡 `Completed — Failed` (yellow)
- ⏳ `Running...` (animated spinner)
- ❌ `Error` (red, with retry option)

### 5.2 Scenario Picker Modal

```
┌─────────────────────────────────────────────────┐
│ Run A2A Simulation                          [X] │
├─────────────────────────────────────────────────┤
│                                                 │
│  ⚡ Build Custom Simulation (Recommended)       │
│  ┌─────────────────────────────────────────┐    │
│  │ Simulate a negotiation between you and  │    │
│  │ this contact using real CRM data.       │    │
│  │                                         │    │
│  │ Type: [Sales Call         ▼]            │    │
│  │                                         │    │
│  │ Your Profile (auto-filled):             │    │
│  │   Name:    [You / logged-in user   ]    │    │
│  │   Role:    [Account Executive      ]    │    │
│  │   Goals:   [Close at $80K+         ]    │    │
│  │                                         │    │
│  │ Their Profile (from Contact):           │    │
│  │   Name:    [Jane Smith             ]    │    │
│  │   Role:    [CTO                    ]    │    │
│  │   Company: [Acme Corp              ]    │    │
│  │   Industry:[Fintech                ]    │    │
│  │                                         │    │
│  │ Deal Context:                           │    │
│  │   Value:   [$500,000               ]    │    │
│  │   Stage:   [Negotiation            ]    │    │
│  │                                         │    │
│  │ Additional notes: [                ]    │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  ── OR pick a pre-built scenario ──             │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │ 🎯 Investor Pitch                       │    │
│  │ Simulate a Series A pitch meeting       │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ 💼 Enterprise B2B Sales                  │    │
│  │ SaaS contract negotiation               │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│              [Cancel]  [▶ Start Simulation]      │
└─────────────────────────────────────────────────┘
```

---

## 6. Data Storage Policy

**The CRM stores pointers, not data.** A2A is the single source of truth for all simulation data.

### What the CRM stores (per simulation record on the Contact entity):

| Field | Type | Source |
|---|---|---|
| `session_id` | string | From `POST /simulate` response |
| `scenario_id` | string | From `POST /simulate` request |
| `scenario_name` | string | From `GET /scenarios` or `POST /simulate` response |
| `status` | enum | `running` → `completed` / `failed` (updated via polling or webhook) |
| `deal_status` | enum | `Agreed` / `Blocked` / `Failed` / `null` (from outcome) |
| `outcome_summary` | text | 1-2 sentence summary from outcome (e.g., "Deal reached at €125K") |
| `viewer_url` | url | Link to A2A Glass Box viewer |
| `turns_completed` | int | From outcome |
| `created_at` | datetime | When simulation was triggered |
| `completed_at` | datetime | When simulation finished |

### What the CRM does NOT store:

- Full negotiation transcripts
- Agent reasoning / inner thoughts
- Detailed evaluation scores or dimensions
- Participant summaries (beyond the outcome_summary)
- Raw session data, agent_states, or agent_memories
- Hidden context, custom prompts, or model overrides

### Why:

- **Single source of truth**: All rich data lives in A2A. No sync issues.
- **Thin plugin**: Less CRM storage, less maintenance, less data migration risk.
- **Privacy**: Sensitive AI reasoning never leaves the A2A platform.
- **Access**: The `viewer_url` is the bridge — click it, see everything in the Glass Box.

---

## 7. Error Handling

| Error | Plugin Behavior |
|---|---|
| Invalid API key (401) | Show "Invalid API key" in config panel. Block simulation attempts. |
| Rate limit exceeded (429) | Show "Daily simulation limit reached. Resets at midnight UTC." |
| Scenario not found (404) | Remove scenario from picker, refresh list. |
| A2A server unavailable (5xx) | Show "Simulation service temporarily unavailable. Try again later." |
| Simulation creation failed | Show error message, allow retry. Do not create simulation record. |
| Polling timeout (>10 min) | Stop polling, mark as "Unknown" status, show "Check A2A dashboard" link. |
| Webhook delivery failed | A2A retries 3x with exponential backoff. Plugin falls back to polling. |

---

## 8. Testing Checklist

Before releasing any CRM plugin:

- [ ] API key configuration and secure storage
- [ ] Connection test succeeds/fails appropriately
- [ ] Scenario list fetches and displays correctly
- [ ] Context auto-fill from CRM entity fields
- [ ] Simulation creation returns session_id and viewer URL
- [ ] Status polling updates simulation record on completion
- [ ] Viewer URL opens Glass Box in new tab
- [ ] Error states display user-friendly messages
- [ ] Non-admin users cannot see/modify API key
- [ ] ACL/permissions control who can trigger simulations
- [ ] Multiple simulations on same Contact work correctly
- [ ] Plugin works with both cloud and self-hosted A2A instances

---

## 9. Future Enhancements (Post-v1)

- **Inline results panel**: Show outcome summary, evaluation scores, and participant summaries directly in CRM without opening Glass Box
- **Webhook receiver**: Real-time completion notifications instead of polling
- **Batch simulations**: Run multiple scenario variations from a single trigger
- **Deal-level simulations**: Attach simulations to Deal/Opportunity objects, not just Contacts
- **Simulation comparison**: Side-by-side comparison of multiple simulation runs with different toggles
- **CRM activity logging**: Auto-create CRM activity/note when simulation completes
- **Slack/Teams notification**: Notify sales rep when simulation finishes
