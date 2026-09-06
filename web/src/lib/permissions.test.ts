import { can } from "./permissions";

test("can consulta la lista de capacidades", () => {
  expect(can(["fence:read", "fence:write"], "fence:write")).toBe(true);
  expect(can(["fence:read"], "fence:write")).toBe(false);
  expect(can(undefined, "fence:read")).toBe(false);
});
