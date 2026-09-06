import { z } from "zod";
import type { Fence } from "@/api/hooks";

export const actionValues = ["message", "notify", "locate", "lock", "reboot", "clear_passcode", "wipe", "set_compliance", "custom"] as const;
export const whenValues = ["on_enter", "on_exit", "on_violation", "on_unknown"] as const;

const actionSchema = z.object({ action: z.enum(actionValues), when: z.enum(whenValues), text: z.string(), enabled: z.boolean() });

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
function nonNegativeIntOrEmpty(min: number) {
  return z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? undefined : v),
    z.coerce.number("Debe ser un número").int("Debe ser un número entero").min(min, `Debe ser mayor o igual que ${min}`).optional(),
  );
}

// Fix round 1 (M1-R25 punto 5): fenceFormSchema no recibe `t` (es un const
// exportado, no una función), así que estos mensajes van fijos en español;
// si en un hito futuro el esquema pasa a construirse con `t`, deberían
// sustituirse por claves i18n.
export const fenceFormSchema = z
  .object({
    name: z.string().trim().min(1, "El nombre es obligatorio"),
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/, "Usa minúsculas, dígitos y guiones, empezando por letra o dígito"),
    kind: z.enum(["circle", "polygon"]),
    centerLat: z.coerce.number("La latitud debe ser un número").min(-90, "La latitud debe estar entre -90 y 90").max(90, "La latitud debe estar entre -90 y 90"),
    centerLng: z.coerce.number("La longitud debe ser un número").min(-180, "La longitud debe estar entre -180 y 180").max(180, "La longitud debe estar entre -180 y 180"),
    radiusM: z.coerce.number("El radio debe ser un número"),
    polygonText: z.string(),
    actions: z.array(actionSchema),
    // M1-R25 punto 1: opcionales para no perder `rules` al reeditar una
    // geocerca que no las usa; "" en el input se trata como "sin definir".
    violationIntervalCycles: nonNegativeIntOrEmpty(0),
    dwellSeconds: nonNegativeIntOrEmpty(0),
  })
  .refine((f) => f.kind !== "circle" || f.radiusM > 0, { path: ["radiusM"], message: "El radio debe ser mayor que 0" })
  .refine((f) => f.kind !== "polygon" || parsePolygon(f.polygonText) !== null, { path: ["polygonText"], message: "polygon" });

export type FenceForm = z.infer<typeof fenceFormSchema>;

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
    actions: form.actions.map((a) => ({ action: a.action, when: a.when, enabled: a.enabled, params: a.text ? { text: a.text } : {} })),
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
    actions: (f.actions ?? []).map((a) => ({
      action: a.action as (typeof actionValues)[number],
      when: a.when as (typeof whenValues)[number],
      text: typeof a.params?.text === "string" ? a.params.text : typeof a.params?.msg === "string" ? a.params.msg : "",
      enabled: a.enabled,
    })),
    violationIntervalCycles: f.rules?.violation_interval_cycles,
    dwellSeconds: f.rules?.dwell_seconds,
  };
}
