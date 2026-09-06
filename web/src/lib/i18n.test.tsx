import { renderHook, act } from "@testing-library/react";
import { I18nProvider, useT, useLang, es, en, detectLang } from "./i18n";

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
