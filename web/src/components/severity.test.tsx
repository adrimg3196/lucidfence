import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { SeverityBadge } from "./SeverityBadge";
import { RiskScore } from "./RiskScore";

test("SeverityBadge traduce las cuatro severidades y pinta lo desconocido en neutro", () => {
  renderWithProviders(
    <>
      <SeverityBadge severity="low" />
      <SeverityBadge severity="medium" />
      <SeverityBadge severity="high" />
      <SeverityBadge severity="critical" />
      <SeverityBadge severity="" />
    </>,
  );
  for (const texto of ["Bajo", "Medio", "Alto", "Crítico", "Sin evaluar"]) {
    expect(screen.getByText(texto)).toBeInTheDocument();
  }
  expect(screen.getByText("Sin evaluar").className).toContain("bg-bg-2");
  expect(screen.getByText("Sin evaluar").className).not.toContain("sev-low");
  expect(screen.getByText("Crítico").className).toContain("sev-critical");
});

test("RiskScore con score nulo dice Sin evaluar y no pinta un cero", () => {
  renderWithProviders(<RiskScore score={null} />);
  expect(screen.getByText("Sin evaluar")).toBeInTheDocument();
  expect(screen.queryByText("0")).toBeNull();
});

test("RiskScore con cero muestra el cero y el tono bajo", () => {
  renderWithProviders(<RiskScore score={0} />);
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.getByText("Bajo")).toBeInTheDocument();
  expect(screen.queryByText("Sin evaluar")).toBeNull();
});

test("RiskScore respeta la severidad del servidor por encima de la puntuación", () => {
  renderWithProviders(<RiskScore score={42} severity="critical" />);
  expect(screen.getByText("42")).toBeInTheDocument();
  expect(screen.getByText("Crítico")).toBeInTheDocument();
  expect(screen.queryByText("Medio")).toBeNull();
});

test("RiskScore redondea la puntuación para la tabla", () => {
  renderWithProviders(<RiskScore score={61.4} />);
  expect(screen.getByText("61")).toBeInTheDocument();
  expect(screen.getByText("Alto")).toBeInTheDocument();
});
