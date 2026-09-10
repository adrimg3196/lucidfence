import { makeEnforcementSchema, makeRiskSchema } from "./settingsForm";

const t = ((k: string) => k) as never;

test("un enfriamiento vacío no vale 0", () => {
  const base = { mode: "observe", liveActions: [], allowWipe: false, wipeAllowlist: [] };
  for (const v of ["", "  ", null, undefined]) {
    expect(makeEnforcementSchema(t).safeParse({ ...base, actionCooldownSeconds: v }).success).toBe(false);
  }
  expect(makeEnforcementSchema(t).safeParse({ ...base, actionCooldownSeconds: "900" })).toMatchObject({
    success: true,
    data: { actionCooldownSeconds: 900 },
  });
});

test("un peso o una hora vacíos tampoco valen 0", () => {
  const base = { shiftZones: [], zoneRisk: [], offHoursStart: 20, offHoursEnd: 7 };
  expect(makeRiskSchema(t).safeParse({ ...base, offHoursStart: "" }).success).toBe(false);
  expect(makeRiskSchema(t).safeParse({ ...base, zoneRisk: [{ fenceId: "hq", weight: "" }] }).success).toBe(false);
  expect(makeRiskSchema(t).safeParse({ ...base, zoneRisk: [{ fenceId: "hq", weight: "0.5" }] }).success).toBe(true);
});
