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

export const fenceFormSchema = z
  .object({
    name: z.string().trim().min(1),
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/),
    kind: z.enum(["circle", "polygon"]),
    centerLat: z.coerce.number().min(-90).max(90),
    centerLng: z.coerce.number().min(-180).max(180),
    radiusM: z.coerce.number(),
    polygonText: z.string(),
    actions: z.array(actionSchema),
  })
  .refine((f) => f.kind !== "circle" || f.radiusM > 0, { path: ["radiusM"], message: "radius" })
  .refine((f) => f.kind !== "polygon" || parsePolygon(f.polygonText) !== null, { path: ["polygonText"], message: "polygon" });

export type FenceForm = z.infer<typeof fenceFormSchema>;

export const emptyForm: FenceForm = { name: "", id: "", kind: "circle", centerLat: 40.4168, centerLng: -3.7038, radiusM: 300, polygonText: "", actions: [] };

export function toFence(form: FenceForm): Fence {
  const now = new Date().toISOString();
  const base = {
    id: form.id,
    name: form.name.trim(),
    kind: form.kind,
    rules: {},
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
  };
}
