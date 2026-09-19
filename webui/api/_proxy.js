const RESPONSE_HEADERS = ["content-type", "cache-control", "x-accel-buffering"];

const jsonError = (status, detail, headers) =>
  Response.json(
    { detail },
    {
      status,
      headers: { "Cache-Control": "no-store", ...headers },
    },
  );

// ``cookies``: chuyển cookie của trình duyệt tới dịch vụ và Set-Cookie của dịch vụ về trình duyệt.
// Đường quản trị bật nó cho phiên đăng nhập; đường hỏi đáp bật nó để máy chủ nhận ra câu của quản trị.
export const proxyToBackend = async (
  request,
  { method, path, cookies = false },
  { fetchImpl = globalThis.fetch } = {},
) => {
  if (request.method !== method) {
    return jsonError(405, "Method not allowed.", { Allow: method });
  }

  const baseUrl = (process.env.CLOUD_RUN_SERVICE_URL || "").trim().replace(/\/+$/, "");
  const token = (process.env.BACKEND_API_TOKEN || "").trim();
  if (!baseUrl || !token) return jsonError(500, "Proxy is not configured.");

  let upstreamUrl;
  try {
    upstreamUrl = new URL(`${baseUrl}${path}`);
  } catch {
    return jsonError(500, "Proxy is not configured.");
  }

  const headers = new Headers({ Authorization: `Bearer ${token}` });
  for (const name of ["accept", "content-type", "x-admin-token", ...(cookies ? ["cookie"] : [])]) {
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
  if (cookies) {
    for (const cookie of upstream.headers.getSetCookie?.() ?? []) responseHeaders.append("set-cookie", cookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
};
