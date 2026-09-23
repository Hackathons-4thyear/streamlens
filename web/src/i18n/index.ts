import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { LANGUAGES, resources, type LanguageCode } from "./locales";

const STORAGE_KEY = "streamlens.lang";

function detectLanguage(): LanguageCode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && LANGUAGES.some((l) => l.code === saved)) {
      return saved as LanguageCode;
    }
  } catch {
    // Private browsing, or storage blocked. The default is fine.
  }
  const browser = navigator.language?.slice(0, 2).toLowerCase();
  const match = LANGUAGES.find((l) => l.code === browser);
  return match?.code ?? "en";
}

void i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLanguage(code: LanguageCode): void {
  void i18n.changeLanguage(code);
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // Not being able to remember the choice is survivable.
  }
  document.documentElement.lang = code;
}

document.documentElement.lang = i18n.language;

export default i18n;
export { LANGUAGES };
export type { LanguageCode };
