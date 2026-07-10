import vi from "./vi.json";
import en from "./en.json";

const dict = { vi, en };
export function makeT(lang) {
  return (key) => (dict[lang] || dict.vi)[key] || key;
}
