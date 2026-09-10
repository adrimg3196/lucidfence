import { SeverityBadge } from "./SeverityBadge";
import { useT } from "@/lib/i18n";
import { riskTone, severityTone, type Severity } from "@/lib/severity";
import { cn } from "@/lib/utils";

const color: Record<Severity, string> = {
  low: "text-sev-low",
  medium: "text-sev-medium",
  high: "text-sev-high",
  critical: "text-sev-critical",
  unknown: "text-muted",
};

// score nulo es "no se pudo evaluar", no un cero: se dice con palabras y en
// gris. Un cero inventado haría pasar por sano a un dispositivo sin veredicto.
export function RiskScore({ score, severity }: { score?: number | null; severity?: string | null }) {
  const t = useT();
  if (score == null) return <span className="text-sm text-muted">{t("risk.unevaluated")}</span>;
  const tono = severity ? severityTone(severity) : riskTone(score);
  return (
    <span className="inline-flex items-center gap-2">
      <span className={cn("font-mono text-sm tabular-nums", color[tono])}>{Math.round(score)}</span>
      <SeverityBadge severity={tono} />
    </span>
  );
}
