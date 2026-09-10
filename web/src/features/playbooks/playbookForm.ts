import { z } from "zod";
import type { Playbook } from "@/api/hooks";
import type { Key } from "@/lib/i18n";
import { fromPolicy, toPolicy, type PolicyFormValues } from "@/features/policies/policyForm";

type T = (key: Key, vars?: Record<string, string | number>) => string;

// Playbooks y políticas comparten gramática (T6: "una sola gramática de reglas
// en 2.0"), así que el formulario reutiliza las filas de T23 tal cual: `when` y
// `actions` son exactamente las de PolicyFormValues y las editan ConditionRows
// y ActionRows sin adaptador de por medio.
export type PlaybookFormValues = Pick<PolicyFormValues, "when" | "actions"> & {
  id: string;
  name: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  enabled: boolean;
};

type ConditionRow = PlaybookFormValues["when"][number];
type ActionRow = PlaybookFormValues["actions"][number];

export const emptyPlaybookForm: PlaybookFormValues = {
  id: "",
  name: "",
  description: "",
  severity: "high",
  enabled: true,
  when: [],
  actions: [],
};

// destructiveActions es la copia en el frontend de action.Destructive()
// (internal/domain/action): las cuatro acciones que abren handoff en vez de
// ejecutarse. Vive aquí una sola vez; la lista y el editor la comparten.
export const destructiveActions = ["lock", "wipe", "clear_passcode", "reboot"] as const;

export function destructiveIn(rows: readonly { action?: string }[]): string[] {
  const seen: string[] = [];
  for (const r of rows) {
    const a = r.action ?? "";
    if ((destructiveActions as readonly string[]).includes(a) && !seen.includes(a)) seen.push(a);
  }
  return seen;
}

// Las filas ya las valida el esquema de T23 dentro de ConditionRows/ActionRows;
// aquí solo se exige que existan (playbook.Validate del servidor rechaza tanto
// `when` como `actions` vacíos) y se validan los campos propios del playbook.
export function makePlaybookFormSchema(t: T) {
  return z.object({
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/, t("playbook.error.idFormat")),
    name: z.string().trim().min(1, t("playbook.error.nameRequired")),
    description: z.string(),
    severity: z.enum(["low", "medium", "high", "critical"]),
    enabled: z.boolean(),
    when: z.array(z.custom<ConditionRow>()).min(1, t("playbook.error.whenRequired")),
    actions: z.array(z.custom<ActionRow>()).min(1, t("playbook.error.actionsRequired")),
  });
}

// toPlaybook delega en toPolicy la traducción de filas a condiciones y acciones
// (misma gramática, misma normalización de valores) y se queda solo con esas
// dos claves: un Playbook no tiene `source` ni `template_id`.
export function toPlaybook(v: PlaybookFormValues, now: string): Playbook {
  const shared = toPolicy({ ...(v as unknown as PolicyFormValues) }, now);
  return {
    id: v.id,
    name: v.name.trim(),
    description: v.description.trim(),
    severity: v.severity,
    enabled: v.enabled,
    when: shared.when,
    actions: shared.actions,
    created_at: now,
    updated_at: now,
  };
}

export function fromPlaybook(p: Playbook): PlaybookFormValues {
  const shared = fromPolicy(p as unknown as Parameters<typeof fromPolicy>[0]);
  return {
    id: p.id,
    name: p.name,
    description: p.description ?? "",
    severity: (p.severity ?? "high") as PlaybookFormValues["severity"],
    enabled: p.enabled,
    when: shared.when,
    actions: shared.actions,
  };
}
