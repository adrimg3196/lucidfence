import { z } from "zod";
import type { Policy, PolicyAction, PolicyCondition } from "@/api/hooks";
import type { Key } from "@/lib/i18n";

type T = (key: Key, vars?: Record<string, string | number>) => string;

// Las nueve acciones del dominio (internal/domain/action/action.go). La lista
// es local porque un enum de OpenAPI no existe en tiempo de ejecución, pero
// está atada al tipo generado por los dos lados: `satisfies` impide inventar
// una acción y `actionsCovered` no compila si el dominio gana una y aquí falta.
export const actionValues = ["notify", "message", "locate", "lock", "reboot", "clear_passcode", "set_compliance", "wipe", "custom"] as const satisfies readonly PolicyAction["action"][];
export const actionsCovered: [Exclude<PolicyAction["action"], (typeof actionValues)[number]>] extends [never] ? true : never = true;

// Espejo de action.Destructive() (spec §6.5): estas cuatro exigen haber
// ejecutado el what-if antes de poder guardar la política.
export const destructiveActions: readonly string[] = ["lock", "wipe", "clear_passcode", "reboot"];
export function isDestructive(a: string): boolean {
  return destructiveActions.includes(a);
}

export const severityValues = ["low", "medium", "high", "critical"] as const;

export type ValueKind = "number" | "boolean" | "list" | "text";

const signalPrefix = "signal:";
// Hojas cuyo valor es numérico o booleano. Es una heurística de presentación
// (qué control se pinta y cómo se reconstruye el valor), no un vocabulario:
// un campo desconocido cae en "text" y se guarda como texto, que es lo que
// hace el dominio con cualquier valor que no sabe comparar.
const numericLeaves = ["risk_score", "score", "route_deviation_m", "dwell_seconds", "battery_level", "storage_free_gb", "storage_total_gb", "zone_risk", "speed_kmh", "distance_km", "hour"];
const booleanLeaves = ["compliant", "encryption_enabled", "rooted", "os_outdated", "osquery_config_valid", "suspicious", "shift_match", "shift_known", "verified", "off_hours"];

export function leafOf(field: string): string {
  const bare = field.startsWith(signalPrefix) ? field.slice(signalPrefix.length) : field;
  const dot = bare.lastIndexOf(".");
  return dot === -1 ? bare : bare.slice(dot + 1);
}

export function kindForField(field: string, op: string): ValueKind {
  if (op === "in") return "list";
  const leaf = leafOf(field);
  if (numericLeaves.includes(leaf)) return "number";
  if (booleanLeaves.includes(leaf)) return "boolean";
  return "text";
}

// kindOfValue gana a kindForField al cargar una política: el tipo real del
// JSON es la verdad, y así guardar sin tocar nada devuelve lo mismo que llegó.
export function kindOfValue(v: unknown, field: string, op: string): ValueKind {
  if (Array.isArray(v)) return "list";
  if (typeof v === "number") return "number";
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "string") return "text";
  return kindForField(field, op);
}

export function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.map((x) => String(x)).join(", ");
  if (v === null || v === undefined) return "";
  return String(v);
}

export function parseValue(text: string, kind: ValueKind, field: string): unknown {
  const raw = text.trim();
  if (kind === "number") return Number(raw);
  if (kind === "boolean") return raw === "true";
  if (kind === "list") {
    const items = raw.split(",").map((s) => s.trim()).filter((s) => s !== "");
    return kindForField(field, "eq") === "number" ? items.map(Number) : items;
  }
  return text;
}

const conditionRow = z
  .object({
    field: z.string(),
    op: z.string(),
    value: z.string(),
    kind: z.enum(["number", "boolean", "list", "text"]),
  });

export function makePolicyFormSchema(t: T) {
  return z.object({
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/, t("policy.error.idFormat")),
    name: z.string().trim().min(1, t("policy.error.nameRequired")),
    description: z.string(),
    severity: z.enum(severityValues),
    enabled: z.boolean(),
    when: z
      .array(
        conditionRow.superRefine((row, ctx) => {
          if (row.field.trim() === "") {
            ctx.addIssue({ code: "custom", path: ["field"], message: t("policy.error.fieldRequired") });
          }
          if (row.kind === "number" && (row.value.trim() === "" || !Number.isFinite(Number(row.value.trim())))) {
            ctx.addIssue({ code: "custom", path: ["value"], message: t("policy.error.notANumber") });
          }
        }),
      )
      .min(1, t("policy.error.whenRequired")),
    // Ruling M2-R11: policy.Validate (T4) rechaza `actions` vacío ("'actions'
    // debe ser una lista no vacía"), así que el editor lo exige también, con
    // la misma forma que playbook.error.actionsRequired (T25).
    actions: z
      .array(
        z.object({
          action: z.enum(actionValues),
          text: z.string(),
          textKey: z.string(),
          params: z.record(z.string(), z.unknown()),
          hadParams: z.boolean(),
        }),
      )
      .min(1, t("policy.error.actionsRequired")),
    source: z.string(),
    templateId: z.string(),
    createdAt: z.string(),
  });
}

export type PolicyFormValues = z.infer<ReturnType<typeof makePolicyFormSchema>>;
export type ConditionRow = PolicyFormValues["when"][number];
export type ActionRow = PolicyFormValues["actions"][number];

export const emptyPolicyForm: PolicyFormValues = {
  id: "",
  name: "",
  description: "",
  severity: "medium",
  enabled: true,
  when: [],
  actions: [],
  source: "",
  templateId: "",
  createdAt: "",
};

// toAction sobrescribe solo la clave de texto que edita el formulario y deja
// el resto de params intacto (mismo contrato que fenceForm.ts, M1-R27 C11).
// `hadParams` recuerda si la acción traía el objeto: así un {"params":{}} de
// plantilla vuelve a salir vacío en vez de desaparecer.
function toAction(r: ActionRow): PolicyAction {
  const params: Record<string, unknown> = { ...r.params };
  const key = r.textKey || "text";
  if (r.text) params[key] = r.text;
  else delete params[key];
  const out: PolicyAction = { action: r.action };
  if (Object.keys(params).length > 0 || r.hadParams) out.params = params;
  return out;
}

function fromAction(a: PolicyAction): ActionRow {
  const params = (a.params ?? {}) as Record<string, unknown>;
  const textKey = typeof params.text === "string" ? "text" : typeof params.msg === "string" ? "msg" : "text";
  const text = params[textKey];
  return { action: a.action, text: typeof text === "string" ? text : "", textKey, params, hadParams: a.params !== undefined };
}

// simulationKey es la firma de lo que el what-if simula: `when` (cuándo
// dispara) y `actions` (qué hace). La puerta del editor no es "se ha simulado
// alguna vez" sino "se ha simulado ESTO". Fuera quedan los sellos de tiempo
// —`toPolicy` los rehace en cada render y la puerta no se abriría jamás— y
// el nombre, la descripción, la severidad y `enabled`, que no mueven ni un
// disparo del resultado y solo harían pedir una simulación de más.
export function simulationKey(p: Policy): string {
  return JSON.stringify({ when: p.when, actions: p.actions });
}

export function toPolicy(v: PolicyFormValues, now: string): Policy {
  const out: Policy = {
    id: v.id,
    name: v.name.trim(),
    when: v.when.map((r) => ({ field: r.field, op: r.op as PolicyCondition["op"], value: parseValue(r.value, r.kind, r.field) })),
    actions: v.actions.map(toAction),
    enabled: v.enabled,
    severity: v.severity,
    created_at: v.createdAt || now,
    updated_at: now,
  };
  if (v.description) out.description = v.description;
  if (v.source) out.source = v.source;
  if (v.templateId) out.template_id = v.templateId;
  return out;
}

export function fromPolicy(p: Policy): PolicyFormValues {
  const severity = (severityValues as readonly string[]).includes(p.severity) ? (p.severity as PolicyFormValues["severity"]) : "medium";
  return {
    id: p.id,
    name: p.name,
    description: p.description ?? "",
    severity,
    enabled: p.enabled,
    when: (p.when ?? []).map((c) => ({ field: c.field, op: c.op as string, value: formatValue(c.value), kind: kindOfValue(c.value, c.field, c.op) })),
    actions: (p.actions ?? []).map(fromAction),
    source: p.source ?? "",
    templateId: p.template_id ?? "",
    createdAt: p.created_at,
  };
}

// label busca la clave y, si el diccionario no la tiene, devuelve el texto
// crudo: `t` devuelve la propia clave cuando falta, y una clave suelta en
// pantalla es peor que el nombre técnico del campo.
function label(t: T, key: string, raw: string): string {
  const out = t(key as Key);
  return out === key ? raw : out;
}

export function describeCondition(c: PolicyCondition, t: T): string {
  const field = label(t, `policy.field.${leafOf(c.field)}`, c.field);
  const op = label(t, `policy.op.${c.op}`, c.op);
  return `${field} ${op} ${describeValue(c.value, t)}`;
}

function describeValue(v: unknown, t: T): string {
  if (typeof v === "boolean") return v ? t("common.yes") : t("common.no");
  if (Array.isArray(v)) return v.map((x) => describeValue(x, t)).join(", ");
  if (typeof v === "string") return label(t, `policy.value.${v}`, v);
  return formatValue(v);
}
