import { renderHook, act } from "@testing-library/react";
import { I18nProvider, useT, useLang, es, en, detectLang, type Key } from "./i18n";

test("traduce, interpola y cambia de idioma", () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => <I18nProvider initial="es">{children}</I18nProvider>;
  const { result } = renderHook(() => ({ t: useT(), lang: useLang() }), { wrapper });
  expect(result.current.t("nav.devices")).toBe("Dispositivos");
  expect(result.current.t("fences.delete.confirm", { name: "HQ" })).toBe("¿Eliminar la geocerca HQ?");
  act(() => result.current.lang.setLang("en"));
  expect(result.current.t("nav.devices")).toBe("Devices");
});

test("los diccionarios tienen las mismas claves", () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort());
});

test("detectLang ignora el navegador y usa español por defecto (M1-R20)", () => {
  localStorage.clear();
  const original = Object.getOwnPropertyDescriptor(window.navigator, "language");
  Object.defineProperty(window.navigator, "language", { value: "en-US", configurable: true });
  try {
    expect(detectLang()).toBe("es");
  } finally {
    if (original) Object.defineProperty(window.navigator, "language", original);
  }
});

test("detectLang respeta la preferencia guardada", () => {
  localStorage.setItem("lf.lang", "en");
  expect(detectLang()).toBe("en");
  localStorage.clear();
});

test("los bloques de M2 existen en los dos diccionarios y ninguna clave queda vacía", () => {
  for (const prefix of ["nav.", "risk.", "policy.", "incident.", "alert.", "playbook.", "handoff.", "event.", "action.", "settings."]) {
    const claves = Object.keys(es).filter((k) => k.startsWith(prefix));
    expect(claves.length, prefix).toBeGreaterThan(0);
    for (const k of claves) expect(en[k as Key], k).toBeTruthy();
  }
  for (const [k, v] of Object.entries(es)) expect(v, k).not.toBe("");
});

test("la severidad sin evaluar no se llama baja en ninguno de los dos idiomas", () => {
  expect(es["risk.severity.unknown"]).toBe("Sin evaluar");
  expect(en["risk.severity.unknown"]).toBe("Not evaluated");
  expect(es["risk.severity.unknown"]).not.toBe(es["risk.severity.low"]);
  expect(en["risk.severity.unknown"]).not.toBe(en["risk.severity.low"]);
});
