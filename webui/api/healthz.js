import { proxyToLightning } from "./_proxy.js";

export const GET = (request) =>
  proxyToLightning(request, { method: "GET", path: "/healthz" });
