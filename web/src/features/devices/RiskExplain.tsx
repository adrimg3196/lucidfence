import { Link } from "react-router";
import { RiskScore } from "@/components/RiskScore";
import { useT } from "@/lib/i18n";
import type { components } from "@/api/schema";

type Verdict = components["schemas"]["Verdict"];
type Signals = { [name: string]: { [key: string]: unknown } | null };

// RiskExplain no repite lo que ya hace RiskScore (T22): la puntuación y su
// insignia de severidad viven ahí, incluido el caso score=null, que RiskScore
// resuelve sin pintar ninguna insignia (nunca "low", nunca verde). Esta pieza
// añade el porqué: el aviso de evaluación fallida, las razones en el orden
// exacto en que las produjo el motor, las políticas que casaron y, de M2-R64,
// la procedencia y la verificación del veredicto (evidenceGate,
// internal/domain/risk/verdict_result.go): sin ellas un 30 sin evidencia se
// lee en pantalla igual que un 30 con cuatro señales detrás.
export function RiskExplain({ verdict, signals }: { verdict: Verdict; signals?: Signals }) {
  const t = useT();
  const signalCount = Object.keys(signals ?? {}).length;
  return (
    <div className="space-y-4">
      <RiskScore score={verdict.score} severity={verdict.severity} />
      {verdict.score == null && <p className="text-sm text-muted">{t("device.risk.unevaluated")}</p>}
      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide text-muted">{t("risk.reasons")}</h3>
        {verdict.reasons.length === 0 ? (
          <p className="mt-1 text-sm text-muted">{t("risk.noReasons")}</p>
        ) : (
          <ol data-testid="risk-reasons" className="mt-1 list-decimal space-y-1 pl-5 text-sm">
            {verdict.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ol>
        )}
      </div>
      {verdict.matched_policies.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted">{t("risk.matchedPolicies")}</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {verdict.matched_policies.map((id) => (
              <li key={id}>
                <Link to={`/policies/${id}`} className="font-mono text-accent hover:underline">
                  {id}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted">
        {t("risk.provenance")}: <span className="font-mono">{verdict.provenance}</span> · {t("risk.verified")}: {verdict.verified ? t("common.yes") : t("common.no")}
      </p>
      {/* M2-R64: un veredicto no verificado con puntuación (provenance
          "context", la razón sintética de evidenceGate) tiene un número en
          pantalla que ninguna señal ni política respalda; se avisa en tono
          neutro, sin alarmar, para que no se lea como un riesgo acreditado. */}
      {!verdict.verified && verdict.score != null && <p className="text-xs text-muted">{t("risk.unverified.warning")}</p>}
      <p className="text-xs text-muted">{t("risk.signalsEvaluated", { count: signalCount })}</p>
    </div>
  );
}
