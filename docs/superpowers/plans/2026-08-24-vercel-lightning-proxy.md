# Vercel Lightning Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route browser health and streamed chat calls through authenticated same-origin Vercel Functions without exposing the Lightning token.

**Architecture:** Plain Vite continues to build static assets. Two files under `webui/api/` use Vercel Web Handlers and a private shared proxy helper to forward requests and return the upstream `ReadableStream` unchanged. Local Vite rewrites `/api/*` to the existing unauthenticated backend paths.

**Tech Stack:** Vite 8, Vercel Functions Web API, Node.js built-in test runner, Playwright

**Spec:** `docs/superpowers/specs/2026-08-24-vercel-lightning-proxy-design.md`

## Global Constraints

- `LIGHTNING_API_BASE_URL` and `LIGHTNING_API_TOKEN` are server-only.
- The browser always calls `/api/healthz` and `/api/chat` without `Authorization`.
- Chat responses must stream without buffering.
- Docker and the Lightning backend source remain unchanged.

---

### Task 1: Authenticated proxy behavior

**Files:**
- Create: `webui/api/_proxy.js`
- Create: `webui/api/healthz.js`
- Create: `webui/api/chat.js`
- Test: `webui/tests/proxy.test.mjs`
- Modify: `webui/package.json`

**Interfaces:**
- Consumes: Web `Request`, `LIGHTNING_API_BASE_URL`, `LIGHTNING_API_TOKEN`
- Produces: `proxyToLightning(request, { method, path }) -> Promise<Response>`, route functions `GET(request)` and `POST(request)`

- [x] Write Node tests against a real local upstream server for method validation, server-side Bearer replacement, status/header forwarding, missing configuration, network failure, and incremental SSE delivery.
- [x] Run `npm run test:proxy` and verify the tests fail because the routes do not exist.
- [x] Implement the minimal shared proxy and route exports; return bounded JSON errors with no secret values.
- [x] Run `npm run test:proxy` and verify all proxy tests pass.

### Task 2: Same-origin browser contract and local development

**Files:**
- Modify: `webui/script.js`
- Modify: `webui/vite.config.js`
- Modify: `webui/playwright.config.js`
- Modify: `webui/tests/ui.spec.mjs`

**Interfaces:**
- Consumes: `/api/healthz`, `/api/chat`
- Produces: browser requests with no credential-bearing headers; local rewrites to `/healthz` and `/chat`

- [x] Change the existing Playwright URL/auth tests to require same-origin `/api/*` requests without `Authorization` and run them to observe failure.
- [x] Remove all `VITE_API_*` client code and use literal `/api/*` paths.
- [x] Configure Vite `server.proxy['/api']` with target `http://127.0.0.1:8000` and a rewrite that removes the `/api` prefix; remove production env validation.
- [x] Run the focused browser tests and then the complete Playwright suite.

### Task 3: Deployment contract documentation

**Files:**
- Modify: `webui/.env.example`
- Modify: `README.md`
- Modify: `webui/vercel.json`

**Interfaces:**
- Consumes: Vercel project with Root Directory `webui`
- Produces: documented server-only environment setup and sufficient chat function duration

- [x] Replace public `VITE_*` examples with `LIGHTNING_API_BASE_URL` and `LIGHTNING_API_TOKEN` instructions.
- [x] Document the Vercel dashboard setup, redeploy order, and why backend CORS is unnecessary.
- [x] Configure a bounded function duration suitable for the streamed chat endpoint.

### Task 4: Verification and handoff

**Files:**
- Verify all modified files and generated bundle only; do not commit `dist/` or test artifacts unless already tracked and intentionally updated.

**Interfaces:**
- Consumes: completed Tasks 1–3
- Produces: deployable Vercel frontend commit

- [x] Run `npm run test:proxy`, `npm test`, and `npm run build` with no `VITE_*` variables.
- [x] Inspect `dist/assets/*.js` to confirm neither the Lightning hostname nor token variable names are embedded.
- [x] Review `git diff --check`, `git diff`, and `git status` before committing.
- [x] Commit in the repository's established imperative sentence style; push only after verification.
