import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { RiskExplain } from "./RiskExplain";
import type { components } from "@/api/schema";

type Verdict = components["schemas"]["Verdict"];

const base: Verdict = { score: null, severity: "unknown", reasons: [], matched_policies: [], provenance: "none", verified: false };

test("score 72 muestra el número, la severidad high y las razones en orden", () => {
  const verdict: Verdict = {
    ...base,
    score: 72,
    severity: "high",
    reasons: ["dispositivo rooteado", "fuera de horario laboral"],
    matched_policies: ["contorno-alto-riesgo"],
    // evidenceGate (internal/domain/risk/verdict_result.go) solo devuelve
    // "tool"+verified:true cuando hay razones (M2-R64).
    provenance: "tool",
    verified: true,
  };
  renderWithProviders(<RiskExplain verdict={verdict} signals={{ device_posture: { rooted: true } }} />);
  expect(screen.getByText("72")).toBeInTheDocument();
  expect(screen.getByText("Alto")).toBeInTheDocument();
  const items = [...screen.getByTestId("risk-reasons").querySelectorAll("li")].map((li) => li.textContent);
  expect(items).toEqual(["dispositivo rooteado", "fuera de horario laboral"]);
});

test("score nulo muestra el aviso de no evaluado con el evaluation_error y ningún tono verde", () => {
  const verdict: Verdict = { ...base, reasons: ["no se pudo evaluar el riesgo: proveedor sin respuesta"] };
  renderWithProviders(<RiskExplain verdict={verdict} signals={{}} />);
  // RiskScore (T22) no pinta ninguna insignia de severidad cuando score es nulo:
  // solo el texto "Sin evaluar" en gris. "Bajo" (el tono verde) no puede
  // aparecer aquí bajo ninguna circunstancia porque no hay insignia que pintar.
  expect(screen.getByText("Sin evaluar")).toBeInTheDocument();
  expect(screen.queryByText("Bajo")).toBeNull();
  expect(screen.getByText(/Sin evaluar: el motor no pudo calcular el riesgo/)).toBeInTheDocument();
  expect(screen.getByText("no se pudo evaluar el riesgo: proveedor sin respuesta")).toBeInTheDocument();
});

test("sin razones muestra el vacío honesto, no inventa explicación y, sin verificar, avisa que la puntuación no tiene señal explícita (M2-R64)", () => {
  const verdict: Verdict = { ...base, score: 12, severity: "low", reasons: [], provenance: "context", verified: false };
  renderWithProviders(<RiskExplain verdict={verdict} signals={{}} />);
  expect(screen.getByText("Sin razones registradas.")).toBeInTheDocument();
  expect(screen.queryByTestId("risk-reasons")).toBeNull();
  expect(screen.getByText(/no tiene una señal explícita detrás/)).toBeInTheDocument();
});

test("las políticas casadas enlazan a /policies/:id", () => {
  const verdict: Verdict = {
    ...base,
    score: 80,
    severity: "critical",
    reasons: ["riesgo crítico"],
    matched_policies: ["fuera-de-turno", "dispositivo-rooteado"],
    provenance: "tool",
    verified: true,
  };
  renderWithProviders(<RiskExplain verdict={verdict} signals={{}} />);
  expect(screen.getByRole("link", { name: "fuera-de-turno" })).toHaveAttribute("href", "/policies/fuera-de-turno");
  expect(screen.getByRole("link", { name: "dispositivo-rooteado" })).toHaveAttribute("href", "/policies/dispositivo-rooteado");
});

test("un veredicto verificado (score>0, con razones) no muestra el aviso de señal no explícita (M2-R64)", () => {
  const verdict: Verdict = { ...base, score: 45, severity: "medium", reasons: ["riesgo de zona"], provenance: "tool", verified: true };
  renderWithProviders(<RiskExplain verdict={verdict} signals={{}} />);
  expect(screen.queryByText(/no tiene una señal explícita detrás/)).toBeNull();
});
