import { z } from "zod";
import type { Fence } from "@/api/hooks";
import type { Key } from "@/lib/i18n";

export const actionValues = ["message", "notify", "locate", "lock", "reboot", "clear_passcode", "wipe", "set_compliance", "custom"] as const;
export const whenValues = ["on_enter", "on_exit", "on_violation", "on_unknown"] as const;

// M1-R27 (C11): el formulario solo edita una clave de texto de `params`
// ("text", o "msg" si la acción ya la traía); `params` guarda el objeto
// completo tal cual llegó, y `textKey` recuerda qué clave sobrescribir al
// reconstruirlo en toFence. El resto de claves (p. ej. `channel`) viaja
// intacto y nunca pasa por la UI.
const actionSchema = z.object({
  action: z.enum(actionValues),
  when: z.enum(whenValues),
  text: z.string(),
  textKey: z.string().optional(),
  params: z.record(z.string(), z.unknown()).optional(),
  enabled: z.boolean(),
});

type T = (key: Key, vars?: Record<string, string | number>) => string;

export function parsePolygon(text: string): { lat: number; lng: number }[] | null {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const pts: { lat: number; lng: number }[] = [];
  for (const line of lines) {
    const [a, b, ...rest] = line.split(",").map((s) => s.trim());
    if (rest.length || a === undefined || b === undefined) return null;
    const lat = Number(a);
    const lng = Number(b);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
    pts.push({ lat, lng });
  }
  return pts.length >= 3 ? pts : null;
}

// nonNegativeIntOrEmpty valida un entero >= min, tratando "" (input vacío)
// como "sin definir" en vez de forzarlo a 0 (M1-R25 punto 1: distingue "no
// tocar la regla" de "ponerla a cero").
function nonNegativeIntOrEmpty(min: number, t: T) {
  return z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? undefined : v),
    z.coerce.number(t("fence.error.notANumber")).int(t("fence.error.notAnInteger")).min(min, t("fence.error.min", { min })).optional(),
  );
}

// M1-R27 (C15): fenceFormSchema tenía sus mensajes fijos en español; ahora
// es una factoría que recibe `t` para que respete el idioma activo. El
// componente la reconstruye con useMemo cuando cambia `t`.
export function makeFenceFormSchema(t: T) {
  return z
    .object({
      name: z.string().trim().min(1, t("fence.error.nameRequired")),
      id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/, t("fence.error.idFormat")),
      kind: z.enum(["circle", "polygon"]),
      centerLat: z.coerce.number(t("fence.error.latNumber")).min(-90, t("fence.error.latRange")).max(90, t("fence.error.latRange")),
      centerLng: z.coerce.number(t("fence.error.lngNumber")).min(-180, t("fence.error.lngRange")).max(180, t("fence.error.lngRange")),
      radiusM: z.coerce.number(t("fence.error.radiusNumber")),
      polygonText: z.string(),
      actions: z.array(actionSchema),
      // M1-R25 punto 1: opcionales para no perder `rules` al reeditar una
      // geocerca que no las usa; "" en el input se trata como "sin definir".
      violationIntervalCycles: nonNegativeIntOrEmpty(0, t),
      dwellSeconds: nonNegativeIntOrEmpty(0, t),
    })
    .refine((f) => f.kind !== "circle" || f.radiusM > 0, { path: ["radiusM"], message: t("fence.error.radiusPositive") })
    .refine((f) => f.kind !== "polygon" || parsePolygon(f.polygonText) !== null, { path: ["polygonText"], message: "polygon" });
}

export type FenceForm = z.infer<ReturnType<typeof makeFenceFormSchema>>;

export const emptyForm: FenceForm = { name: "", id: "", kind: "circle", centerLat: 40.4168, centerLng: -3.7038, radiusM: 300, polygonText: "", actions: [], violationIntervalCycles: undefined, dwellSeconds: undefined };

export function toFence(form: FenceForm): Fence {
  const now = new Date().toISOString();
  // M1-R25 punto 1: PUT reemplaza el registro completo, así que `rules` solo
  // debe llevar las claves que el formulario define explícitamente.
  const rules: Fence["rules"] = {};
  if (form.violationIntervalCycles !== undefined) rules.violation_interval_cycles = form.violationIntervalCycles;
  if (form.dwellSeconds !== undefined) rules.dwell_seconds = form.dwellSeconds;
  const base = {
    id: form.id,
    name: form.name.trim(),
    kind: form.kind,
    rules,
    // M1-R27 (C11): se sobrescribe solo la clave que edita el formulario
    // (a.textKey, "text" por defecto); el resto de `params` viaja intacto en
    // vez de reconstruirse desde cero, así PUT no borra claves como `channel`.
    actions: form.actions.map((a) => ({ action: a.action, when: a.when, enabled: a.enabled, params: { ...(a.params ?? {}), [a.textKey ?? "text"]: a.text } })),
    created_at: now,
    updated_at: now,
  };
  if (form.kind === "circle") return { ...base, center: { lat: form.centerLat, lng: form.centerLng }, radius_m: form.radiusM } as Fence;
  return { ...base, polygon: parsePolygon(form.polygonText) ?? [] } as Fence;
}

export function fromFence(f: Fence): FenceForm {
  return {
    name: f.name,
    id: f.id,
    kind: f.kind,
    centerLat: f.center?.lat ?? emptyForm.centerLat,
    centerLng: f.center?.lng ?? emptyForm.centerLng,
    radiusM: f.radius_m ?? emptyForm.radiusM,
    polygonText: (f.polygon ?? []).map((p) => `${p.lat}, ${p.lng}`).join("\n"),
    // M1-R27 (C11): se conserva el objeto `params` completo y se recuerda en
    // `textKey` cuál de sus claves es la que el formulario edita como texto
    // ("text" si existe, si no "msg" cuando la acción ya la trae, si no
    // "text" por defecto para una acción nueva sin params).
    actions: (f.actions ?? []).map((a) => {
      const params = a.params ?? {};
      const textKey = typeof params.text === "string" ? "text" : typeof params.msg === "string" ? "msg" : "text";
      return {
        action: a.action as (typeof actionValues)[number],
        when: a.when as (typeof whenValues)[number],
        text: typeof params[textKey] === "string" ? (params[textKey] as string) : "",
        textKey,
        params,
        enabled: a.enabled,
      };
    }),
    violationIntervalCycles: f.rules?.violation_interval_cycles,
    dwellSeconds: f.rules?.dwell_seconds,
  };
}
