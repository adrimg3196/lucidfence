import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { ActionResult, Handoff } from "@/api/hooks";
import { useLang, useT, type Key } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

const statusTone = { pending: "warning", approved: "info", rejected: "neutral", executed: "success" } as const;

// resultLine traduce el ActionResult tal cual lo devolvió la API (T20: la
// respuesta lleva el resultado, no un OK). El orden importa: bloqueado por el
// guardarraíl gana a fallo, y dry-run nunca se anuncia como "ejecutado".
function resultKey(r: ActionResult): Key {
  if (r.blocked) return "handoff.result.blocked";
  if (!r.ok) return "handoff.result.failed";
  if (r.dry_run) return "handoff.result.dryRun";
  return "handoff.result.executed";
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-3 border-b border-border py-1.5 text-sm last:border-0">
      <span className="text-muted">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}

export function HandoffCard({ handoff, onApprove, onReject }: { handoff: Handoff; onApprove?: () => void; onReject?: () => void }) {
  const t = useT();
  const { lang } = useLang();
  const r = handoff.result;
  const tone = statusTone[handoff.status as keyof typeof statusTone] ?? "neutral";
  return (
    <article className="rounded-[var(--radius-ui)] border border-border bg-panel p-4">
      <header className="flex flex-wrap items-center gap-2">
        <Link to={`/devices/${handoff.device_id}`} className="font-medium hover:text-accent">
          {handoff.device_name}
        </Link>
        <span className="font-mono text-xs text-muted">{handoff.device_id}</span>
        <SeverityBadge severity={handoff.severity} />
        <Badge variant={tone}>{t(`handoff.status.${handoff.status}`)}</Badge>
        <span className="ml-auto text-sm font-medium">{t(`fence.action.${handoff.action}`)}</span>
      </header>
      <div className="mt-3">
        <Row label={t("handoff.playbook")}>
          {handoff.playbook_name} <span className="font-mono text-xs text-muted">{handoff.playbook_id}</span>
        </Row>
        <Row label={t("handoff.reason")}>{handoff.reason}</Row>
        <Row label={t("handoff.requestedAt")}>{formatDateTime(handoff.requested_at, lang)}</Row>
        {handoff.decided_by && (
          <Row label={t("handoff.decidedBy")}>
            {handoff.decided_by} <span className="text-muted">{formatDateTime(handoff.decided_at, lang)}</span>
          </Row>
        )}
        {handoff.note && <Row label={t("handoff.note")}>{handoff.note}</Row>}
      </div>
      {r && (
        <p className={`mt-3 text-sm ${r.blocked || !r.ok ? "text-sev-high" : "text-fg-2"}`}>
          {t(resultKey(r), { reason: r.error ?? r.error_type ?? "", error: r.error ?? "" })}
          {r.error_type && <span className="ml-2 font-mono text-xs text-muted">{r.error_type}</span>}
        </p>
      )}
      {(onApprove || onReject) && (
        <div className="mt-4 flex gap-2">
          {onApprove && (
            <Button size="sm" onClick={onApprove}>
              {t("handoff.approve")}
            </Button>
          )}
          {onReject && (
            <Button size="sm" variant="secondary" onClick={onReject}>
              {t("handoff.reject")}
            </Button>
          )}
        </div>
      )}
    </article>
  );
}
