import { getCloudRunIdentityToken } from "./_google_identity.js";

const RESPONSE_HEADERS = ["content-type", "cache-control", "x-accel-buffering"];

const jsonError = (status, detail, headers) =>
  Response.json(
    { detail },
    {
      status,
      headers: { "Cache-Control": "no-store", ...headers },
    },
  );

export const proxyToBackend = async (
  request,
  { method, path },
  {
    getIdentityToken = getCloudRunIdentityToken,
    fetchImpl = globalThis.fetch,
  } = {},
) => {
  if (request.method !== method) {
    return jsonError(405, "Method not allowed.", { Allow: method });
  }

  const baseUrl = (process.env.CLOUD_RUN_SERVICE_URL || "").trim().replace(/\/+$/, "");
  if (!baseUrl) return jsonError(500, "Proxy is not configured.");

  let upstreamUrl;
  try {
    upstreamUrl = new URL(`${baseUrl}${path}`);
  } catch {
    return jsonError(500, "Proxy is not configured.");
  }

  let token;
  try {
    token = await getIdentityToken(request);
  } catch {
    return jsonError(502, "Could not authenticate to the backend.");
  }

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  for (const name of ["accept", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  let upstream;
  try {
    upstream = await fetchImpl(upstreamUrl, {
      method,
      headers,
      body: method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer(),
      signal: request.signal,
    });
  } catch {
    return jsonError(502, "Could not reach the backend.");
  }

  const responseHeaders = new Headers();
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
};
