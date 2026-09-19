// Giao diện sáng/tối, dùng chung cho hai trang. Lựa chọn lưu trong localStorage khi trình duyệt cho phép.
const KEY = "themeColor";

const saved = () => {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
};

export const applySavedTheme = () => document.body.classList.toggle("light-theme", saved() === "light_mode");

// Đổi giao diện; trả ``true`` khi đang ở nền sáng.
export const toggleTheme = () => {
  const light = document.body.classList.toggle("light-theme");
  try {
    localStorage.setItem(KEY, light ? "light_mode" : "dark_mode");
  } catch {
    // Không lưu được thì chỉ đổi cho lần mở trang này.
  }
  return light;
};
