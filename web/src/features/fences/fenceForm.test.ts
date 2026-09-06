import { makeFenceFormSchema, parsePolygon, toFence, fromFence, emptyForm } from "./fenceForm";

// Identidad: estos tests solo comprueban success/failure de validación, no
// el texto de los mensajes (eso lo cubre FenceEditorPage.test.tsx, M1-R27 C15).
const t = (key: string) => key;
const fenceFormSchema = makeFenceFormSchema(t);

test("parsePolygon acepta 'lat, lng' por línea y rechaza basura", () => {
  expect(parsePolygon("40.40, -3.72\n40.40,-3.70\n 40.44 , -3.70 ")).toEqual([{ lat: 40.4, lng: -3.72 }, { lat: 40.4, lng: -3.7 }, { lat: 40.44, lng: -3.7 }]);
  expect(parsePolygon("40.40, -3.72\nabc")).toBeNull();
  expect(parsePolygon("1,2\n3,4")).toBeNull();
});

test("schema exige centro y radio en círculo, y 3 vértices en polígono", () => {
  const circle = { ...emptyForm, name: "HQ", id: "hq", kind: "circle" as const, centerLat: 40.42, centerLng: -3.71, radiusM: 300 };
  expect(fenceFormSchema.safeParse(circle).success).toBe(true);
  expect(fenceFormSchema.safeParse({ ...circle, radiusM: 0 }).success).toBe(false);
  const poly = { ...emptyForm, name: "P", id: "p", kind: "polygon" as const, polygonText: "0,0\n0,1\n1,1" };
  expect(fenceFormSchema.safeParse(poly).success).toBe(true);
  expect(fenceFormSchema.safeParse({ ...poly, polygonText: "0,0\n0,1" }).success).toBe(false);
});

test("toFence y fromFence son inversas", () => {
  const form = { ...emptyForm, name: "HQ", id: "hq", kind: "circle" as const, centerLat: 40.42, centerLng: -3.71, radiusM: 300, actions: [{ action: "message" as const, when: "on_enter" as const, text: "hola", enabled: true }] };
  const fence = toFence(form);
  expect(fence).toMatchObject({ id: "hq", kind: "circle", center: { lat: 40.42, lng: -3.71 }, radius_m: 300, actions: [{ action: "message", when: "on_enter", enabled: true, params: { text: "hola" } }] });
  expect(fromFence(fence)).toMatchObject({ name: "HQ", id: "hq", kind: "circle", centerLat: 40.42, radiusM: 300, actions: [{ action: "message", text: "hola" }] });
});

// Fix round 1 (M1-R25, punto 1): PUT reemplaza el registro completo, así que
// editar sin conservar `rules` las borraba. fromFence debe exponerlas y
// toFence debe devolverlas intactas.
test("fromFence expone rules y toFence las conserva sin tocarlas", () => {
  const fence = { ...toFence({ ...emptyForm, name: "HQ", id: "hq" }), rules: { violation_interval_cycles: 3, dwell_seconds: 60 } };
  const form = fromFence(fence);
  expect(form.violationIntervalCycles).toBe(3);
  expect(form.dwellSeconds).toBe(60);
  expect(toFence(form).rules).toEqual({ violation_interval_cycles: 3, dwell_seconds: 60 });
});

test("toFence emite rules vacío cuando el formulario no las define", () => {
  const form = { ...emptyForm, name: "HQ", id: "hq" };
  expect(toFence(form).rules).toEqual({});
});

// M1-R27 (C11): fromFence/toFence colapsaban params a un único `text`,
// borrando cualquier otra clave (p. ej. `channel`) y renombrando `msg` a
// `text`. Reproduce la acción de la seed demo (internal/engine/demo.go:52):
// guardar sin tocar nada debe devolver exactamente los mismos params.
test("toFence conserva íntegros los params de una acción ajenos al campo de texto editable (M1-R27, C11)", () => {
  const fence = {
    id: "demo-hq",
    name: "Demo HQ",
    kind: "circle" as const,
    center: { lat: 40.42, lng: -3.71 },
    radius_m: 300,
    rules: {},
    actions: [{ action: "notify" as const, when: "on_exit" as const, enabled: true, params: { channel: "security", msg: "Dispositivo ha salido de HQ" } }],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  const form = fromFence(fence);
  expect(form.actions[0]).toMatchObject({ text: "Dispositivo ha salido de HQ" });
  expect(toFence(form).actions).toEqual(fence.actions);
});

test("toFence no inventa params en acciones sin texto y omite params vacío (M1-R28)", () => {
  const fence = {
    id: "warehouse-poly",
    name: "Almacén Sur",
    kind: "polygon" as const,
    polygon: [
      { lat: 40.4, lng: -3.7 },
      { lat: 40.41, lng: -3.7 },
      { lat: 40.41, lng: -3.69 },
    ],
    rules: {},
    actions: [{ action: "locate" as const, when: "on_exit" as const, enabled: true }],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  expect(toFence(fromFence(fence)).actions).toEqual(fence.actions);
});

test("vaciar el texto elimina la clave de texto y conserva el resto de params (M1-R28)", () => {
  const fence = {
    id: "demo-hq",
    name: "Demo HQ",
    kind: "circle" as const,
    center: { lat: 40.42, lng: -3.71 },
    radius_m: 300,
    rules: {},
    actions: [{ action: "notify" as const, when: "on_exit" as const, enabled: true, params: { channel: "security", msg: "Fuera" } }],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  const form = fromFence(fence);
  form.actions[0].text = "";
  expect(toFence(form).actions[0].params).toEqual({ channel: "security" });
});
