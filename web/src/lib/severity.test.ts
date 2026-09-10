import { severityOrder, severityTone, riskTone, compareSeverity, severityValues, type Severity } from "./severity";

test("el orden es critical > high > medium > low > unknown", () => {
  const orden: Severity[] = ["critical", "high", "medium", "low", "unknown"];
  for (let i = 1; i < orden.length; i++) {
    expect(severityOrder[orden[i - 1]]).toBeGreaterThan(severityOrder[orden[i]]);
  }
  expect(severityOrder.unknown).toBe(0);
});

test("unknown nunca devuelve el tono de low", () => {
  for (const entrada of ["", "unknown", "desconocido", "none", "bogus", null, undefined]) {
    expect(severityTone(entrada), String(entrada)).toBe("unknown");
  }
  expect(severityOrder[severityTone("unknown")]).not.toBe(severityOrder.low);
});

test("severityTone normaliza mayúsculas y espacios y rechaza lo demás", () => {
  expect(severityTone("LOW ")).toBe("low");
  expect(severityTone(" Critical")).toBe("critical");
  expect(severityTone("medium")).toBe("medium");
  expect(severityTone("high")).toBe("high");
  expect(severityTone("severe")).toBe("unknown");
});

test("riskTone usa los mismos cortes que el motor y distingue nulo de cero", () => {
  expect(riskTone(null)).toBe("unknown");
  expect(riskTone(undefined)).toBe("unknown");
  expect(riskTone(Number.NaN)).toBe("unknown");
  expect(riskTone(0)).toBe("low");
  expect(riskTone(29.9)).toBe("low");
  expect(riskTone(30)).toBe("medium");
  expect(riskTone(54.9)).toBe("medium");
  expect(riskTone(55)).toBe("high");
  expect(riskTone(79.9)).toBe("high");
  expect(riskTone(80)).toBe("critical");
  expect(riskTone(100)).toBe("critical");
});

test("compareSeverity ordena de más grave a menos y deja unknown al final", () => {
  const filas = ["low", "unknown", "critical", "medium", "high"];
  expect([...filas].sort(compareSeverity)).toEqual(["critical", "high", "medium", "low", "unknown"]);
});

test("severityValues enumera las cuatro severidades conocidas, sin unknown (M2-R7)", () => {
  expect(severityValues).toEqual(["low", "medium", "high", "critical"]);
});
