import { describeCondition, emptyPolicyForm, fromPolicy, kindForField, kindOfValue, makePolicyFormSchema, parseValue, simulationKey, toPolicy } from "./policyForm";
import type { Policy } from "@/api/hooks";
import type { Key } from "@/lib/i18n";

// Identidad: estos tests comprueban estructura y success/failure, no el copy
// (eso lo cubren los tests de las vistas). describeCondition sí necesita un
// `t` real, así que se le da un diccionario mínimo con las claves que usa.
const id = (key: string) => key;
const schema = makePolicyFormSchema(id as (k: Key) => string);

const dict: Record<string, string> = {
  "policy.field.route_deviation_m": "desviación de ruta",
  "policy.field.fence_state": "estado de geocerca",
  "policy.op.gt": "mayor que",
  "policy.op.eq": "es",
  "policy.value.outside": "fuera",
  "common.yes": "Sí",
};
const t = ((key: string) => dict[key] ?? key) as (k: Key) => string;

// Política con las cuatro formas de valor, dos formas de params (uno con
// claves y uno vacío), una acción sin params, y los tres campos que la UI
// no edita (description, source, template_id) más created_at.
const policy: Policy = {
  id: "tpl-wipe-rooted-outside",
  name: "Wipe si rooteado fuera de geocerca",
  description: "importada del catálogo de plantillas",
  when: [
    { field: "fence_state", op: "eq", value: "outside" },
    { field: "signal:device_health.rooted", op: "eq", value: true },
    { field: "signal:route_state.route_deviation_m", op: "gt", value: 500 },
    { field: "posture.country", op: "in", value: ["ES", "PT"] },
  ],
  actions: [
    { action: "notify", params: { channel: "ciso", msg: "Crítico: dispositivo rooteado fuera de geocerca" } },
    { action: "wipe", params: {} },
    { action: "locate" },
  ],
  enabled: true,
  severity: "critical",
  source: "template",
  template_id: "tpl-wipe-rooted-outside",
  created_at: "2026-01-02T03:04:05Z",
  updated_at: "2026-01-02T03:04:05Z",
};

test("fromPolicy y toPolicy son inversas y no pierden params ni campos que la UI no edita", () => {
  const back = toPolicy(fromPolicy(policy), "2026-09-06T10:00:00Z");
  expect(back).toEqual({ ...policy, updated_at: "2026-09-06T10:00:00Z" });
});

test("fromPolicy deduce el tipo del valor del JSON, no del nombre del campo", () => {
  const form = fromPolicy(policy);
  expect(form.when.map((r) => r.kind)).toEqual(["text", "boolean", "number", "list"]);
  expect(form.when.map((r) => r.value)).toEqual(["outside", "true", "500", "ES, PT"]);
  expect(form.actions[0]).toMatchObject({ action: "notify", textKey: "msg", text: "Crítico: dispositivo rooteado fuera de geocerca", hadParams: true });
  expect(form.actions[2]).toMatchObject({ action: "locate", text: "", hadParams: false });
});

test("kindForField usa el operador y el nombre del campo, y kindOfValue el tipo real", () => {
  expect(kindForField("signal:route_state.route_deviation_m", "gt")).toBe("number");
  expect(kindForField("posture.rooted", "eq")).toBe("boolean");
  expect(kindForField("posture.country", "in")).toBe("list");
  expect(kindForField("platform", "eq")).toBe("text");
  expect(kindOfValue(3, "campo_que_no_existe", "eq")).toBe("number");
  expect(kindOfValue(null, "risk_score", "gte")).toBe("number");
});

test("parseValue reconstruye el tipo y una lista de un campo numérico son números", () => {
  expect(parseValue("500", "number", "route_deviation_m")).toBe(500);
  expect(parseValue("false", "boolean", "posture.rooted")).toBe(false);
  expect(parseValue(" ES , PT ", "list", "posture.country")).toEqual(["ES", "PT"]);
  expect(parseValue("500, 700", "list", "route_deviation_m")).toEqual([500, 700]);
});

test("el esquema exige nombre, id con formato, al menos una condición, al menos una acción y valor numérico en campo numérico", () => {
  const base = {
    ...emptyPolicyForm,
    name: "Fuera",
    id: "fuera",
    when: [{ field: "fence_state", op: "eq", value: "outside", kind: "text" as const }],
    actions: [{ action: "notify" as const, text: "", textKey: "text", params: {}, hadParams: false }],
  };
  expect(schema.safeParse(base).success).toBe(true);
  expect(schema.safeParse({ ...base, name: "  " }).success).toBe(false);
  expect(schema.safeParse({ ...base, id: "Fuera" }).success).toBe(false);
  expect(schema.safeParse({ ...base, when: [] }).success).toBe(false);
  const numeric = { ...base, when: [{ field: "route_deviation_m", op: "gt", value: "muchos", kind: "number" as const }] };
  const bad = schema.safeParse(numeric);
  expect(bad.success).toBe(false);
  expect(bad.error?.issues[0].path).toEqual(["when", 0, "value"]);
  expect(schema.safeParse({ ...numeric, when: [{ ...numeric.when[0], value: "500" }] }).success).toBe(true);
  // Ruling M2-R11: policy.Validate (T4) rechaza `actions` vacío ("'actions'
  // debe ser una lista no vacía"), así que el formulario también lo exige en
  // vez de dejar que el servidor devuelva un 400 que el editor no sabría
  // señalar.
  expect(schema.safeParse({ ...base, actions: [] }).success).toBe(false);
});

test("describeCondition traduce campo, operador y valor a lenguaje llano", () => {
  expect(describeCondition({ field: "signal:route_state.route_deviation_m", op: "gt", value: 500 }, t)).toBe("desviación de ruta mayor que 500");
  expect(describeCondition({ field: "fence_state", op: "eq", value: "outside" }, t)).toBe("estado de geocerca es fuera");
  // Desviación: el brief escribía aquí "policy.field.rooted es Sí" (la clave
  // sin traducir), que contradice su propio diseño ("si no existe, se
  // muestra el campo crudo en vez de una clave sin traducir", línea 58 y el
  // comentario de la siguiente aserción) y la implementación literal de
  // `label` del Step 3: con "policy.field.rooted" ausente del diccionario,
  // `label` cae al campo crudo (`c.field`), no a la clave.
  expect(describeCondition({ field: "signal:device_health.rooted", op: "eq", value: true }, t)).toBe("signal:device_health.rooted es Sí");
  // Un campo o un operador sin etiqueta se muestran crudos, nunca como una
  // clave i18n suelta (misma corrección que la aserción anterior: el brief
  // escribía aquí "policy.op.eq", la clave, en vez de "eq", el operador crudo).
  expect(describeCondition({ field: "signal:probe.value", op: "eq", value: "x" }, id as (k: Key) => string)).toBe("signal:probe.value eq x");
});

test("simulationKey firma cuándo dispara y qué hace, y nada más", () => {
  const base = toPolicy(fromPolicy(policy), "2026-09-05T00:00:00Z");
  // Los sellos de tiempo se rehacen en cada render del editor: si entraran en
  // la firma, la puerta del what-if no se abriría nunca.
  expect(simulationKey(toPolicy(fromPolicy(policy), "2027-01-01T00:00:00Z"))).toBe(simulationKey(base));
  // El nombre, la severidad y el interruptor no mueven ni un disparo del
  // resultado: pedir otra simulación por ellos sería puro peaje.
  expect(simulationKey({ ...base, name: "otro nombre", severity: "low", enabled: false })).toBe(simulationKey(base));
  // Volver destructiva una acción o mover una condición sí lo cambia todo.
  expect(simulationKey({ ...base, actions: [{ action: "wipe" }] })).not.toBe(simulationKey(base));
  expect(simulationKey({ ...base, when: [{ field: "fence_state", op: "eq", value: "inside" }] })).not.toBe(simulationKey(base));
});
