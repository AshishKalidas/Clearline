# Public demo deployment

[Open Clearline](https://clearline-ecru.vercel.app).

The public deployment runs in the `clearline` project under `ashishkalidas-projects` on Vercel. It needs no visitor account, provider key, database or running development machine. Each browser owns its sample state; decisions are temporary and reset on refresh.

## Runtime boundary

`npm run build:demo` produces a Vite build in `demo` mode. That build exposes only the browser-owned sample workspace, with illustrative reviews, corrections, proof scenarios, activity and published evaluation evidence. Connected navigation is absent; `/workspace/*` URLs redirect to their `/sample/*` equivalents while preserving query parameters and fragments. Legacy review/proof links stay within the sample deployment.

Actual CSV imports, PDF extraction, provider calls, policy-authorized allocations and durable audit records run in the Docker application described in the README. They are not simulated server endpoints on this static deployment. There is no hosted production sign-in or real bank integration.

## Vercel configuration

| Setting | Value |
|---|---|
| Project root | `web` |
| Framework | Vite |
| Node.js | 24.x |
| Install | `npm ci` |
| Build | `npm run build:demo` |
| Output | `dist` |
| Build/runtime credentials | None |

`web/vercel.json` supplies the build settings, security headers and SPA rewrite needed for deep-link refreshes. The repository-root `.vercelignore` limits CLI uploads to frontend source and excludes environment files, generated credentials, dependencies, browser artifacts and backend data. Vercel's local project metadata is ignored by Git and both Docker contexts.

From the repository root, with Vercel CLI authenticated to the project owner:

```bash
vercel link --yes --scope ashishkalidas-projects --project clearline
vercel deploy --dry --json --scope ashishkalidas-projects
vercel deploy --prod --yes --scope ashishkalidas-projects
```

The first release was deployed directly with the CLI. The Vercel GitHub integration did not accept the repository connection, so pushes do not automatically publish a new demo. Use the commands above to release subsequent changes unless that integration is connected later.

## Verification

```bash
cd web
npm ci
npm test
npx playwright install chromium
npm run test:demo
CLEARLINE_DEMO_URL=https://clearline-ecru.vercel.app npm run test:demo
```

The demo browser suite verifies anonymous navigation, deep-link refreshes, review/activity updates, proof scenarios, evidence access, legacy/connected redirects and phone layouts. It blocks and counts `/api/` requests to verify that no backend is required. GitHub Actions runs the same suite locally alongside the full Docker application checks.
