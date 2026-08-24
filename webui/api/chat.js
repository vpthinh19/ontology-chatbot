import { proxyToLightning } from "./_proxy.js";

export const POST = (request) =>
  proxyToLightning(request, { method: "POST", path: "/chat" });
