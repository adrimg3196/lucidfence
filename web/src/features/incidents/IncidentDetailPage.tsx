import { useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useIncident, useMe, usePatchIncident, type Incident } from "@/api/hooks";
import { useLang, useT } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { IncidentTimeline } from "./IncidentTimeline";

const statusVariant = { open: "danger", ack: "warning", closed: "neutral" } as const;

export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const t = useT();
  const { lang } = useLang();
  const incident = useIncident(id);
  const patch = usePatchIncident();
  const me = useMe();
  const canWrite = can(me.data?.capabilities, "incident:write");
  const [closing, setClosing] = useState(false);
  const [note, setNote] = useState("");
  if (incident.isPending) return <Loading rows={6} />;
  if (incident.error) return <ErrorState error={incident.error} onRetry={() => incident.refetch()} />;
  const inc = incident.data!;
  const fields: [string, string][] = [
    [t("incident.opened"), formatDateTime(inc.opened_at, lang)],
    [t("incident.updated"), formatDateTime(inc.updated_at, lang)],
    [t("incident.count"), String(inc.count)],
    [t("incident.risk"), inc.risk_score == null ? t("severity.unknown") : String(inc.risk_score)],
  ];
  // Cerrar exige nota; reconocer y reabrir son inmediatos (el 1.x sella la
  // nota en la transición, tests/test_qa_incidents.py). usePatchIncident
  // (T22) manda { id, patch: IncidentPatch }: ver "Desviaciones" del informe.
  const transition = (status: Incident["status"]) => patch.mutate({ id: inc.id, patch: { status } });
  return (
    <div className="space-y-6">
      <Link to="/incidents" className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> {t("incident.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{inc.title}</h1>
        <SeverityBadge severity={inc.severity} />
        <Badge variant={statusVariant[inc.status]}>{t(`incident.status.${inc.status}` as never)}</Badge>
        <span className="font-mono text-xs text-muted">{inc.kind}</span>
      </div>
      {canWrite && (
        <div className="flex flex-wrap gap-2">
          {inc.status === "open" && (
            <Button disabled={patch.isPending} onClick={() => transition("ack")}>
              {t("incident.ack")}
            </Button>
          )}
          {inc.status !== "closed" && (
            <Button variant="secondary" disabled={patch.isPending} onClick={() => setClosing(true)}>
              {t("incident.close")}
            </Button>
          )}
          {inc.status === "closed" && (
            <Button variant="secondary" disabled={patch.isPending} onClick={() => transition("open")}>
              {t("incident.reopen")}
            </Button>
          )}
        </div>
      )}
      {patch.error && <ErrorState error={patch.error} />}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("incident.recommendation")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-fg-2">{inc.recommendation}</p>
            <p className="text-sm">
              <span className="text-muted">{t("incident.device")}: </span>
              <Link to={`/devices/${inc.device_id}`} className="font-medium hover:text-accent">
                {inc.device_name}
              </Link>
            </p>
            <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
              {fields.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-border py-1.5">
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right">{v}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("incident.evidence")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 font-mono text-xs text-fg-2">
              {inc.evidence.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>{t("incident.timeline")}</CardTitle>
          </CardHeader>
          <CardContent>
            <IncidentTimeline entries={inc.timeline} />
          </CardContent>
        </Card>
      </div>
      <ConfirmDialog
        open={closing}
        onOpenChange={(o) => {
          setClosing(o);
          if (!o) setNote("");
        }}
        title={t("incident.close.title")}
        description={t("incident.close.help")}
        confirmLabel={t("incident.close")}
        cancelLabel={t("incident.cancel")}
        confirmDisabled={patch.isPending || note.trim() === ""}
        onConfirm={() =>
          patch.mutate(
            { id: inc.id, patch: { status: "closed", note: note.trim() } },
            {
              onSuccess: () => {
                setClosing(false);
                setNote("");
              },
            },
          )
        }
      >
        <div className="mt-4 space-y-1.5">
          <Label htmlFor="note">{t("incident.note")}</Label>
          <textarea
            id="note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-[var(--radius-ui)] border border-border bg-panel p-2 text-sm"
          />
        </div>
        {patch.error && <ErrorState error={patch.error} />}
      </ConfirmDialog>
    </div>
  );
}
