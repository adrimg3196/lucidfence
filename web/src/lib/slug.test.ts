import { slugify } from "./slug";

test("slugify", () => {
  expect(slugify("Demo HQ · Madrid")).toBe("demo-hq-madrid");
  expect(slugify("  Almacén Sur  ")).toBe("almacen-sur");
  expect(slugify("---")).toBe("");
});
