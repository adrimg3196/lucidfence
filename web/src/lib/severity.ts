// Tono compartido de las severidades del motor (internal/domain/risk, T3).
// `unknown` es su propio tono, nunca el de `low`: un riesgo que no se pudo
// evaluar se pinta neutro y jamás verde, porque un dispositivo sin veredicto
// no puede parecer un dispositivo sano.
export type Severity = "low" | "medium" | "high" | "critical" | "unknown";

export const severityOrder: Record<Severity, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  unknown: 0,
};

// M2-R7: lista ordenada de las cuatro severidades conocidas (sin `unknown`),
// para quien necesita iterarlas en vez de pesarlas (T24 recorre esta lista en
// vez de `Object.keys(severityOrder)`, que traería `unknown` de propina).
export const severityValues = ["low", "medium", "high", "critical"] as const;

const conocidas = new Set<string>(["low", "medium", "high", "critical"]);

// severityTone normaliza lo que venga del servidor (o del formulario) a uno de
// los cinco tonos. Cualquier cosa que no sea una severidad conocida es unknown.
export function severityTone(s: string | null | undefined): Severity {
  const v = (s ?? "").trim().toLowerCase();
  return conocidas.has(v) ? (v as Severity) : "unknown";
}

// riskTone replica los cortes de risk.Severity en Go: >=80 critical, >=55 high,
// >=30 medium y el resto low. Solo se usa cuando no hay severidad del servidor
// (por ejemplo, las muestras del what-if); si la hay, manda ella.
export function riskTone(score: number | null | undefined): Severity {
  if (score == null || Number.isNaN(score)) return "unknown";
  if (score >= 80) return "critical";
  if (score >= 55) return "high";
  if (score >= 30) return "medium";
  return "low";
}

// compareSeverity ordena de más grave a menos grave, con unknown al final.
export function compareSeverity(a: string, b: string): number {
  return severityOrder[severityTone(b)] - severityOrder[severityTone(a)];
}
