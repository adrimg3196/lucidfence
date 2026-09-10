import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
import { severityTone, type Severity } from "@/lib/severity";
import { cn } from "@/lib/utils";

const variante: Record<Severity, "neutral" | "success" | "warning" | "danger"> = {
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "danger",
  unknown: "neutral",
};

// `badge.tsx` no tiene variante `critical` y esta tarea no lo toca: la crítica
// parte de `danger` y se repinta con su token propio, más oscuro que `high`.
const extra: Record<Severity, string> = {
  low: "",
  medium: "",
  high: "",
  critical: "bg-sev-critical/15 text-sev-critical",
  unknown: "",
};

export function SeverityBadge({ severity, className }: { severity?: string | null; className?: string }) {
  const t = useT();
  const s = severityTone(severity);
  return (
    <Badge variant={variante[s]} className={cn(extra[s], className)}>
      {t(`risk.severity.${s}`)}
    </Badge>
  );
}
