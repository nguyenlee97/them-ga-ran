export const vnd = (n) => (n || 0).toLocaleString("vi-VN") + " đ";

export function timeOfDay(d = new Date()) {
  const h = d.getHours();
  if (h < 10) return "breakfast";
  if (h < 14) return "lunch";
  if (h < 17) return "afternoon";
  if (h < 21) return "dinner";
  return "late";
}

export const dayOfWeek = (d = new Date()) =>
  ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()];

export const uuid = () =>
  (crypto.randomUUID && crypto.randomUUID()) ||
  "id-" + Math.random().toString(36).slice(2) + Date.now();
