import { proxyToBackend } from "./_proxy.js";

export const POST = (request) =>
  proxyToBackend(request, { method: "POST", path: "/chat" });
