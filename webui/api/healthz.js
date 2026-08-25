import { proxyToBackend } from "./_proxy.js";

export const GET = (request) =>
  proxyToBackend(request, { method: "GET", path: "/healthz" });
