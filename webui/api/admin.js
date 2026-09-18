import { proxyToBackend } from "./_proxy.js";

// vercel.json viết lại /api/admin/<đường> thành /api/admin?path=<đường>, nên một hàm lo
// mọi đường quản trị. Đường chỉ gồm chữ, số, gạch nối và gạch chéo, để yêu cầu gửi đi
// không thể thoát khỏi /admin.
const SAFE_PATH = /^[A-Za-z0-9_\-/]*$/;

const handle = (request) => {
  const url = new URL(request.url);
  const path = (url.searchParams.get("path") || "").replace(/^\/+/, "");
  if (!SAFE_PATH.test(path)) {
    return Response.json({ detail: "Đường không hợp lệ." }, { status: 400 });
  }
  url.searchParams.delete("path");
  const query = url.searchParams.toString();
  return proxyToBackend(request, {
    method: request.method,
    path: `/admin/${path}${query ? `?${query}` : ""}`,
    cookies: true,
  });
};

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
