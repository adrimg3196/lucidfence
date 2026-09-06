import { renderHook, act } from "@testing-library/react";
import { I18nProvider, useT, useLang, es, en } from "./i18n";

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
