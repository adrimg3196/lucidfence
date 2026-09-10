import { z } from "zod";
import type { EgressSettings, EnforcementSettings, Settings, WebhookSettings } from "@/api/hooks";
import type { Key } from "@/lib/i18n";

type T = (key: Key, vars?: Record<string, string | number>) => string;

// numeroDeCampo protege a los cuatro campos numéricos del formulario de
// ajustes. react-hook-form entrega "" desde un <input type="number"> vacío
// (los controles se registran sin valueAsNumber) y z.coerce.number() lo
// convierte en 0 sin error: vaciar el enfriamiento y guardar apagaba el
// guardarraíl de cooldown en silencio. El preprocess convierte el vacío
// -y el nulo- en NaN, que z.number() sí rechaza, así que el mensaje de
// error que ya existía por fin se ve.
function numeroDeCampo(msg: string, min: number, max?: number, entero = true) {
  let n = z.coerce.number(msg).min(min, msg);
  if (entero) n = n.int(msg);
  if (max !== undefined) n = n.max(max, msg);
  return z.preprocess((v) => (v === null || v === undefined || (typeof v === "string" && v.trim() === "") ? NaN : v), n);
}

// PUT /api/v1/settings/risk (T21) ya está en el contrato y en schema.d.ts,
// pero T22 no exportó un alias propio para su cuerpo (solo lo hizo para
// enforcement/webhook/egress). Derivarlo de Settings["risk"] en vez de
// importar "@/api/schema" a mano mantiene a hooks.ts como la única puerta de
// tipos sin tocar ese fichero (fuera del alcance de esta tarea).
export type RiskSettings = Settings["risk"];

// Mismo orden que action.All (internal/domain/action, M1): lock, wipe,
// message, locate, reboot, clear_passcode, set_compliance, custom, notify.
// Las etiquetas reutilizan fence.action.* (M1): T22 deja fijado que estas
// claves no se duplican para el registro de acciones ni para el selector de
// acciones en vivo de enforcement.
export const actionOptions = ["lock", "wipe", "message", "locate", "reboot", "clear_passcode", "set_compliance", "custom", "notify"] as const;

export const webhookEventOptions = ["incident.opened", "incident.closed", "handoff.pending", "action.executed", "alert.fired"] as const;

export type EnforcementFormValues = {
  mode: "observe" | "enforce";
  liveActions: (typeof actionOptions)[number][];
  allowWipe: boolean;
  wipeAllowlist: { value: string }[];
  actionCooldownSeconds: number;
};

export function makeEnforcementSchema(t: T) {
  return z.object({
    mode: z.enum(["observe", "enforce"]),
    liveActions: z.array(z.enum(actionOptions)),
    allowWipe: z.boolean(),
    wipeAllowlist: z.array(z.object({ value: z.string().trim().min(1, t("settings.enforcement.wipeAllowlist.required")) })),
    actionCooldownSeconds: numeroDeCampo(t("settings.error.cooldown"), 0),
  });
}

export function toEnforcement(v: EnforcementFormValues): EnforcementSettings {
  return {
    mode: v.mode,
    live_actions: v.liveActions,
    allow_wipe: v.allowWipe,
    wipe_allowlist: v.wipeAllowlist.map((w) => w.value.trim()),
    action_cooldown_seconds: v.actionCooldownSeconds,
  };
}

export function fromEnforcement(e: EnforcementSettings): EnforcementFormValues {
  return {
    mode: e.mode as EnforcementFormValues["mode"],
    liveActions: (e.live_actions ?? []) as EnforcementFormValues["liveActions"],
    allowWipe: e.allow_wipe,
    wipeAllowlist: (e.wipe_allowlist ?? []).map((value) => ({ value })),
    actionCooldownSeconds: e.action_cooldown_seconds,
  };
}

export type WebhookFormValues = {
  url: string;
  format: "native" | "ocsf";
  events: string[];
  enabled: boolean;
  // El secreto nunca llega del servidor (GET solo manda secret_set, spec
  // §5.2): el formulario siempre arranca con "" y secretTouched distingue
  // "no lo toqué" (no se envía) de "lo vacié a propósito" (se envía "").
  secret: string;
  secretTouched: boolean;
};

export function makeWebhookSchema(t: T) {
  return z
    .object({
      url: z.string().trim(),
      format: z.enum(["native", "ocsf"]),
      events: z.array(z.enum(webhookEventOptions)),
      enabled: z.boolean(),
      secret: z.string(),
      secretTouched: z.boolean(),
    })
    .refine((v) => v.url === "" || v.url.startsWith("https://"), { path: ["url"], message: t("settings.error.url") })
    .refine((v) => !v.enabled || v.url !== "", { path: ["url"], message: t("settings.error.url") });
}

export function fromWebhook(w: WebhookSettings): WebhookFormValues {
  return { url: w.url, format: w.format as WebhookFormValues["format"], events: w.events, enabled: w.enabled, secret: "", secretTouched: false };
}

// El PUT real (T21: WebhookSettingsUpdate) lleva `secret` opcional y nunca
// `secret_set`; T22 tipó useUpdateWebhooks(body: WebhookSettings), la forma
// de LECTURA (secret_set obligatorio, sin secret). Esta tarea respeta el
// contrato de red real de T21 y lo hace compilar con un cast documentado, en
// vez de fabricar un `secret_set` que el formulario no calcula ni el
// servidor necesita en la escritura, o de reabrir la firma de T22.
export function toWebhook(v: WebhookFormValues): WebhookSettings {
  const base = { url: v.url.trim(), format: v.format, events: v.events, enabled: v.enabled };
  return (v.secretTouched ? { ...base, secret: v.secret } : base) as WebhookSettings;
}

// El canal ntfy (spec §4.1 y §6.4) contra PUT /api/v1/settings/ntfy. Mismo
// patrón de tres estados que el secreto del webhook: el token nunca llega
// del servidor (GET solo manda token_set), el formulario arranca con "" y
// tokenTouched distingue "no lo toqué" (no se envía) de "lo vacié a
// propósito" (se envía "").
export type NtfySettings = Settings["ntfy"];
export type NtfyUpdate = Omit<NtfySettings, "token_set"> & { token?: string };

export type NtfyFormValues = { url: string; enabled: boolean; token: string; tokenTouched: boolean };

export function makeNtfySchema(t: T) {
  return z
    .object({ url: z.string().trim(), enabled: z.boolean(), token: z.string(), tokenTouched: z.boolean() })
    .refine((v) => v.url === "" || v.url.startsWith("https://"), { path: ["url"], message: t("settings.error.url") })
    .refine((v) => !v.enabled || v.url !== "", { path: ["url"], message: t("settings.error.url") });
}

export function fromNtfy(n: NtfySettings): NtfyFormValues {
  return { url: n.url, enabled: n.enabled, token: "", tokenTouched: false };
}

export function toNtfy(v: NtfyFormValues): NtfyUpdate {
  const base = { url: v.url.trim(), enabled: v.enabled };
  return v.tokenTouched ? { ...base, token: v.token } : base;
}

export type EgressFormValues = { hosts: { value: string }[]; allowPrivate: boolean };

export function makeEgressSchema(t: T) {
  return z.object({
    hosts: z.array(z.object({ value: z.string().trim().min(1, t("settings.error.host")) })),
    allowPrivate: z.boolean(),
  });
}

export function fromEgress(e: EgressSettings): EgressFormValues {
  return { hosts: e.hosts.map((value) => ({ value })), allowPrivate: e.allow_private };
}

export function toEgress(v: EgressFormValues): EgressSettings {
  return { hosts: v.hosts.map((h) => h.value.trim()), allow_private: v.allowPrivate };
}

// M2-C3: bloque de contexto de riesgo (turnos, riesgo por zona, franja fuera
// de turno) contra PUT /api/v1/settings/risk (T21). shift_zones empareja un
// id de DISPOSITIVO con la GEOCERCA donde se le espera durante su turno —no
// "geocerca→turno": verificado contra internal/domain/settings/settings.go:97
// (`a.Risk.ShiftZones["dev-1"] = "demo-hq"` en su propio test) y contra
// internal/engine/risk.go:31-34, que copia ShiftZones tal cual a la señal
// shift_match (signals.go:136, `ctx.ShiftZones[d.ID]`). zone_risk empareja
// una geocerca con el peso 0-1 que suma a la puntuación (signals.go:186).
export type RiskFormValues = {
  shiftZones: { deviceId: string; fenceId: string }[];
  zoneRisk: { fenceId: string; weight: number }[];
  offHoursStart: number;
  offHoursEnd: number;
};

export function makeRiskSchema(t: T) {
  return z.object({
    shiftZones: z.array(
      z.object({
        deviceId: z.string().trim().min(1, t("settings.risk.error.deviceId")),
        fenceId: z.string().trim().min(1, t("settings.risk.error.fenceId")),
      }),
    ),
    zoneRisk: z.array(
      z.object({
        fenceId: z.string().trim().min(1, t("settings.risk.error.fenceId")),
        weight: numeroDeCampo(t("settings.risk.error.weight"), 0, 1, false),
      }),
    ),
    offHoursStart: numeroDeCampo(t("settings.risk.error.offHours"), 0, 23),
    offHoursEnd: numeroDeCampo(t("settings.risk.error.offHours"), 0, 23),
  });
}

// El orden de un Record no es contractual; se ordena por clave para que la
// lista no reordene sus filas entre un guardado y la siguiente carga.
export function fromRisk(r: RiskSettings): RiskFormValues {
  return {
    shiftZones: Object.entries(r.shift_zones)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([deviceId, fenceId]) => ({ deviceId, fenceId })),
    zoneRisk: Object.entries(r.zone_risk)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fenceId, weight]) => ({ fenceId, weight })),
    offHoursStart: r.off_hours_start,
    offHoursEnd: r.off_hours_end,
  };
}

export function toRisk(v: RiskFormValues): RiskSettings {
  return {
    shift_zones: Object.fromEntries(v.shiftZones.map((s) => [s.deviceId.trim(), s.fenceId.trim()])),
    zone_risk: Object.fromEntries(v.zoneRisk.map((z) => [z.fenceId.trim(), z.weight])),
    off_hours_start: v.offHoursStart,
    off_hours_end: v.offHoursEnd,
  };
}
