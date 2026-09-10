import { alertKindKeys, alertKinds, alertUnitKeys, emptyAlertForm, fromRule, makeAlertFormSchema, toRule } from "./alertForm";
import { es } from "@/lib/i18n";

const t = ((key: keyof typeof es) => es[key]) as never;
const schema = makeAlertFormSchema(t);

test("cada tipo tiene etiqueta y unidad", () => {
  expect(alertKinds).toEqual(["outside_duration", "risk_above", "noncompliant", "battery_below", "storage_low", "stale_checkin"]);
  for (const k of alertKinds) {
    expect(es[alertKindKeys[k]]).toBeTruthy();
    expect(es[alertUnitKeys[k]]).toBeTruthy();
  }
  expect(alertUnitKeys.outside_duration).toBe("alert.unit.minutes");
  expect(alertUnitKeys.battery_below).toBe("alert.unit.percent");
  expect(alertUnitKeys.storage_low).toBe("alert.unit.gb");
  expect(alertUnitKeys.noncompliant).toBe("alert.unit.none");
});

test("el umbral vacío, no numérico o negativo se rechaza con su mensaje", () => {
  const base = { ...emptyAlertForm, id: "fuera-30", name: "Fuera 30 min" };
  expect(schema.safeParse(base).success).toBe(true);
  const vacio = schema.safeParse({ ...base, threshold: "" });
  expect(vacio.success).toBe(false);
  expect(vacio.error!.issues[0].message).toBe("El umbral debe ser un número");
  const negativo = schema.safeParse({ ...base, threshold: -5 });
  expect(negativo.success).toBe(false);
  expect(negativo.error!.issues[0].message).toBe("El umbral no puede ser negativo");
});

test("la escala 0-100 solo acota riesgo y batería", () => {
  const riesgo = { ...emptyAlertForm, id: "r", name: "Riesgo", kind: "risk_above" as const, threshold: 101 };
  const fallo = schema.safeParse(riesgo);
  expect(fallo.success).toBe(false);
  expect(fallo.error!.issues[0].message).toBe("El umbral no puede pasar de 100");
  // 512 GB libres es un umbral legítimo (mismo criterio que alert.Rule.Validate)
  expect(schema.safeParse({ ...riesgo, kind: "storage_low" as const, threshold: 512 }).success).toBe(true);
});

test("toRule y fromRule son inversas y noncompliant no lleva umbral", () => {
  const values = { id: "bateria-20", name: "  Batería baja  ", kind: "battery_below" as const, threshold: 20, severity: "high" as const, enabled: true };
  expect(toRule(values)).toEqual({ id: "bateria-20", name: "Batería baja", kind: "battery_below", threshold: 20, severity: "high", enabled: true });
  expect(toRule({ ...values, kind: "noncompliant", threshold: 42 }).threshold).toBe(0);
  const rule = { id: "x", name: "X", kind: "risk_above" as const, threshold: 80, severity: "critical", enabled: false, created_at: "2026-09-06T10:00:00Z", updated_at: "2026-09-06T10:00:00Z" };
  expect(fromRule(rule)).toEqual({ id: "x", name: "X", kind: "risk_above", threshold: 80, severity: "critical", enabled: false });
  // una severidad que el servidor no debería mandar cae a "medium" en vez de romper el select
  expect(fromRule({ ...rule, severity: "urgente" }).severity).toBe("medium");
});
