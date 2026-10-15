# Workspace design and interaction

The October 2026 workspace update follows the supplied `APPLE_DESIGN_SYSTEM.md` reference. It uses a system font stack, neutral surfaces, blue actions, semantic status colors, concentric corners and 240 ms UI transitions. No Apple fonts, trademarks, photography or SF Symbols are redistributed; Clearline retains its own mark and SVG icons.

## Materials and accessibility

Liquid Glass is a CSS approximation on the floating sidebar, top toolbar and mobile navigation. It combines translucent tint, `saturate(180%) blur(20px)`, an inset specular rim and restrained depth. Financial cards, evidence, forms and receipts remain opaque. Glass surfaces do not overlap one another. Unsupported backdrop filtering and reduced transparency fall back to opaque chrome; increased contrast removes blur and strengthens boundaries. Reduced motion disables transitions. Controls have visible four-pixel focus rings and 44-pixel targets. Appearance follows the system or a saved light/dark preference, restored before React renders to avoid a theme flash.

The primary responsive boundaries are 1068 px and 734 px. Small screens use a floating bottom navigation, stacked cards and stacked review actions. Native radio controls provide keyboard behavior for appearance and sample-proof choices.

## Routes

React Router's declarative routes are pinned to a React 18-compatible version. Navigation uses real links. The nginx and Vite history fallback allows direct visits and refreshes on nested URLs.

| Route | Behavior |
|---|---|
| `/` | Redirect to `/sample/overview` |
| `/sample/overview` | Illustrative financial summary and sample activity |
| `/sample/review/:proposalId?` | Local sample queue, evidence and temporary decisions |
| `/sample/proofs` | Three explicitly simulated claim-verification scenarios |
| `/sample/activity` | Sample events, including temporary review decisions |
| `/sample/settings` | Reviewer identity, appearance and sample reset |
| `/workspace/overview` | API-backed summary and live panel |
| `/workspace/review/:proposalId?` | Actual proposal details and validated review actions |
| `/workspace/proofs` | Actual PDF extraction and imported-bank verification |
| `/workspace/activity` | Latest 20 meaningful audited events |
| `/workspace/settings` | Local API mutation key, reviewer and appearance |
| `/review`, `/proofs` | Compatibility redirects to connected views |
| Unknown page or proposal | Recoverable not-found state; no silent substitution |

Selected rows create explicit payment links; choosing a tab pins an implicit first selection into its URL. The review URL stores selected proposal, evidence/audit tab, search and decision filters. Loading a queue never redirects the browser. Browser back/forward preserves that context. Changing modes preserves the current page category and clears source-specific proposal IDs and query state. Page titles and the main focus target follow navigation.

## Sample isolation

The sample adapter is a disposable in-memory store containing eight pending examples, three illustrative settlements, open invoice choices, tool evidence and proof outcomes. Its metrics derive from that store. It never delegates to `fetch`, reads a provider key or calls a model. Approve/reject/correct simulate validation and update local balances/events; sample reset restores the initial examples. Refreshing the page or leaving/re-entering sample mode creates a new sample. Appearance persists in localStorage; reviewer identity and the connected mutation key use sessionStorage.

Sample evidence and confidence are illustrative, not generated model output. Sample proof checks inspect no uploaded document. Persistent labels distinguish the sample from the API-backed workspace. The sample fixtures are separate from the 400-case evaluation dataset and are not evaluation evidence.

Each mode owns a separately keyed provider and request adapter. Switching modes aborts outstanding reads and disposes the previous snapshot. The connected workspace never fills an unavailable API with sample values. A failed refresh retains a clearly labeled last successful snapshot, or displays empty placeholders if no request has succeeded.

## Live panel

Connected mode reads `/healthz`, `/metrics`, `/proposals`, `/bank-lines?limit=1000` and `/activity?limit=20`. Reads have an eight-second cancellation deadline. A successful or failed batch schedules its next read after ten seconds, avoiding overlapping polling. Users can pause automatic updates, resume, or refresh once while paused. Leaving the workspace cancels timers and reads. Already submitted review writes can finish, but their completion cannot navigate an unmounted review page.

`GET /activity` is a bounded, read-only projection of audit events. It excludes verbose tool-call events and full payloads, orders by actual event timestamp/ID, and masks text fields before returning summaries. Each proposal event can link to its full audit tab. The panel reports configured provider, last successful sync in Africa/Johannesburg and connection health. It polls committed state; it is not a token stream or a real bank connection. The loaded transfer sum is explicitly not an account balance; only the first 1000 observations are loaded.

## Verification

Unit checks cover sample network isolation, temporary allocation validation, missing-proposal handling, route selection and offline source switching. Browser checks cover real connected approval/rejection/correction/uploads, entirely offline sample actions/proofs, deep-link refresh, query/history navigation, dark preference persistence, mobile overflow, focus/reduced-motion/increased-contrast behavior, and actual live-panel values/pause/recovery.

Screenshots in `docs/images/` are captured from the running app. The live-provider and synthetic evaluation boundaries described in the README remain unchanged.
