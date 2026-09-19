// Gọi đường /api/admin của máy chủ. Lỗi thành Error mang status, errors, details, confirm của máy chủ.

let unauthorized = () => {};
// Phiên hết hạn (401): trang về tài khoản khách.
export const onUnauthorized = (handler) => {
  unauthorized = handler;
};

export const api = async (path, { method = "GET", body } = {}) => {
  const response = await fetch(`/api/admin${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  // Phiên đăng nhập hết hạn giữa chừng: về tài khoản khách thay vì báo lỗi khó hiểu.
  if (response.status === 401) unauthorized();
  if (!response.ok) {
    const error = new Error(data.detail || `Máy chủ trả lỗi ${response.status}.`);
    Object.assign(error, {
      status: response.status,
      errors: data.errors || [],
      details: data.details || [],
      confirm: Boolean(data.confirm),
    });
    throw error;
  }
  return data;
};
