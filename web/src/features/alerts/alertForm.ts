import { z } from "zod";
import type { AlertRule } from "@/api/hooks";
import type { Key } from "@/lib/i18n";

export const alertKinds = ["outside_duration", "risk_above", "noncompliant", "battery_below", "storage_low", "stale_checkin"] as const;
export const severityValues = ["low", "medium", "high", "critical"] as const;

export const alertKindKeys: Record<AlertRule["kind"], Key> = {
  outside_duration: "alert.kind.outside_duration",
  risk_above: "alert.kind.risk_above",
  noncompliant: "alert.kind.noncompliant",
  battery_below: "alert.kind.battery_below",
  storage_low: "alert.kind.storage_low",
  stale_checkin: "alert.kind.stale_checkin",
};

// La unidad va en la etiqueta del campo, no en el placeholder: un umbral sin
// unidad es la forma más rápida de configurar "30 GB" donde se querían "30
// minutos". `noncompliant` no tiene umbral y se envía siempre 0.
export const alertUnitKeys: Record<AlertRule["kind"], Key> = {
  outside_duration: "alert.unit.minutes",
  risk_above: "alert.unit.score",
  noncompliant: "alert.unit.none",
  battery_below: "alert.unit.percent",
  storage_low: "alert.unit.gb",
  stale_checkin: "alert.unit.minutes",
};

// Mismo criterio que alert.Rule.validateThreshold (T5): solo riesgo y batería
// viven en la escala 0-100; 512 GB libres o 4320 minutos son legítimos.
const percentKinds: readonly AlertRule["kind"][] = ["risk_above", "battery_below"];

type T = (key: Key, vars?: Record<string, string | number>) => string;

// El input numérico devuelve "" cuando se vacía, y Number("") es 0: sin este
// preprocesado un umbral vacío se guardaría como 0 en silencio.
function threshold(t: T) {
  return z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? Number.NaN : v),
    z.coerce.number(t("alert.error.thresholdNumber")).min(0, t("alert.error.thresholdNegative")),
  );
}

export function makeAlertFormSchema(t: T) {
  return z
    .object({
      id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/, t("alert.error.idFormat")),
      name: z.string().trim().min(1, t("alert.error.nameRequired")),
      kind: z.enum(alertKinds),
      threshold: threshold(t),
      severity: z.enum(severityValues),
      enabled: z.boolean(),
    })
    .refine((v) => !percentKinds.includes(v.kind) || v.threshold <= 100, {
      path: ["threshold"],
      message: t("alert.error.thresholdPercent"),
    });
}

export type AlertFormValues = z.infer<ReturnType<typeof makeAlertFormSchema>>;

export const emptyAlertForm: AlertFormValues = {
  id: "",
  name: "",
  kind: "outside_duration",
  threshold: 30,
  severity: "medium",
  enabled: true,
};

// created_at/updated_at los sella el servidor (crud[T].stamp de M1); mandarlos
// desde el navegador solo serviría para discutir con el reloj del servidor.
export function toRule(v: AlertFormValues): AlertRule {
  return {
    id: v.id,
    name: v.name.trim(),
    kind: v.kind,
    threshold: v.kind === "noncompliant" ? 0 : v.threshold,
    severity: v.severity,
    enabled: v.enabled,
  };
}

export function fromRule(r: AlertRule): AlertFormValues {
  const severity = (severityValues as readonly string[]).includes(r.severity) ? (r.severity as AlertFormValues["severity"]) : "medium";
  return { id: r.id, name: r.name, kind: r.kind, threshold: r.threshold, severity, enabled: r.enabled };
}
