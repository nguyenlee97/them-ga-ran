/**
 * The real KFC VN site publishes combo composition as a `+`-separated
 * description. Normalize it into Product.comboItems without guessing SKUs.
 * The original description remains the customer-facing source text.
 */
export function comboItemsFromDescription(description = "") {
  return String(description)
    .split(/\s+\+\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const match = part.match(/^(\d+)\s+(.+)$/u);
      return match
        ? { qty: Number(match[1]), note: match[2].trim() }
        : { qty: 1, note: part };
    });
}
