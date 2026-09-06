import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { es, type Key } from "./i18n.es";
import { en } from "./i18n.en";

// M1-R27: los diccionarios viven en i18n.es.ts/i18n.en.ts (este fichero
// rozaba el límite de 300 líneas de un .tsx, spec §9.1); i18n.tsx sigue
// siendo la única API pública y se reexportan aquí para no romper a nadie
// que importe `es`/`en`/`Key` desde "@/lib/i18n".
export { es, en };
export type { Key };
export type Lang = "es" | "en";

const dicts: Record<Lang, Record<Key, string>> = { es, en };

// M1-R20: español por defecto, sin autodetección del navegador
// (constraints.md: la UI arranca en español; el inglés solo llega vía el
// toggle. navigator.language no se consulta nunca).
export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem("lf.lang");
    if (saved === "es" || saved === "en") return saved;
  } catch {
    /* sin storage */
  }
  return "es";
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Record<string, string | number>) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? detectLang());
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("lf.lang", l);
    } catch {
      /* sin storage */
    }
  }, []);
  const t = useCallback(
    (key: Key, vars?: Record<string, string | number>) => {
      let s: string = dicts[lang][key] ?? key;
      for (const [k, v] of Object.entries(vars ?? {})) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useT fuera de I18nProvider");
  return ctx;
}

export function useT() {
  return useI18n().t;
}

export function useLang() {
  const { lang, setLang } = useI18n();
  return { lang, setLang };
}
