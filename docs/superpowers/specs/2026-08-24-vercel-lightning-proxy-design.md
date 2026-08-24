# Vercel-to-Lightning authenticated proxy

## Goal

Keep the Lightning deployment protected by `TokenAuth` without exposing its
Bearer token in the Vite bundle, while preserving the current scale-to-zero
health checks and streamed chat responses.

## Architecture

The browser will call two same-origin endpoints on Vercel:

- `GET /api/healthz`
- `POST /api/chat`

Vercel Functions will forward those requests to the configured Lightning
deployment and add the configured Bearer token on the server. The browser
will never receive the Lightning token or call the Lightning hostname directly.
Because the browser and proxy share an origin, browser CORS preflights no longer
cross the Lightning gateway.

The proxy will use two server-only Vercel environment variables:

- `LIGHTNING_API_BASE_URL`: the Lightning deployment URL, without a trailing
  slash.
- `LIGHTNING_API_TOKEN`: the value configured for Lightning `TokenAuth`.

Neither variable may use the `VITE_` prefix. `VITE_API_BASE_URL` and
`VITE_API_KEY` will be removed from the client contract.

## Request flow

For health checks, the function accepts only `GET`, forwards the request to
`${LIGHTNING_API_BASE_URL}/healthz`, and returns the upstream status and body.

For chat, the function accepts only `POST`, forwards the JSON body to
`${LIGHTNING_API_BASE_URL}/chat`, and pipes the upstream response body to the
browser as it arrives. It must not buffer the SSE response. Relevant headers,
including `Content-Type`, `Cache-Control`, and `X-Accel-Buffering`, are preserved;
hop-by-hop headers are not forwarded.

Both functions overwrite, rather than forward, any browser-supplied
`Authorization` header. Missing proxy configuration returns a generic `500`
without printing secrets. Network failures return `502`. Upstream statuses such
as `401`, `403`, `429`, `502`, and `503` pass through so the existing frontend
state machine can report blocked, busy, and cold-start states correctly.

## Local development

The frontend always calls `/api/healthz` and `/api/chat`. Vite proxies `/api` to
`http://127.0.0.1:8000` and removes the `/api` prefix, so `npm run dev` continues
to use a local backend without Vercel, CORS, or a Lightning token.

Developers who want to exercise the real Vercel Functions locally can use
`vercel dev` with the same two server-only variables, but that is optional and
is not the default frontend workflow.

## Vercel configuration

The Vercel project root remains `webui`. The owner will add
`LIGHTNING_API_BASE_URL` and `LIGHTNING_API_TOKEN` in Project Settings →
Environment Variables for Production and Preview, mark the token sensitive, and
redeploy. Updating a Vercel environment variable does not change an already
built deployment.

After the proxy deployment succeeds, Lightning `TokenAuth` can be enabled. The
backend does not need `ONTCHATBOT_CORS_ORIGINS` for the Vercel frontend because
only the server-to-server proxy calls Lightning.

## Tests and acceptance

Automated tests will verify that:

- every proxied request receives the server-side Bearer token;
- a client-supplied authorization value cannot override it;
- `/api/chat` streams chunks instead of buffering the full response;
- unsupported methods, missing configuration, and upstream network failures
  return bounded, non-secret errors;
- the browser uses same-origin `/api` paths in both health and chat flows;
- the Vite development proxy rewrites `/api/healthz` and `/api/chat` to the
  existing local backend endpoints;
- the existing cold-start, retry, cancellation, SSE, and UI tests remain green.

Manual acceptance consists of enabling Lightning `TokenAuth`, deploying the
frontend, observing a successful health transition after a cold start, and
receiving one complete streamed chat response without a browser CORS error.

## User operations after implementation

The repository will document the dashboard steps, but the required interaction
is limited to:

1. Open the Vercel project and set its Root Directory to `webui` if it is not
   already set.
2. Add the two server-only variables for Production and Preview.
3. Redeploy the latest commit.
4. Re-enable `TokenAuth` on the Lightning deployment using the same token stored
   in `LIGHTNING_API_TOKEN`.
