import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useIncidentAnalytics, useMe } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { severityTone, severityValues } from "@/lib/severity";

const toneColor: Record<string, string> = {
  low: "var(--color-sev-low)",
  medium: "var(--color-sev-medium)",
  high: "var(--color-sev-high)",
  critical: "var(--color-sev-critical)",
  unknown: "var(--color-muted)",
};

// El MTTR nulo es "no lo hemos medido", no "cero segundos": pintar 0 s sería
// un falso verde (1.x tests/test_incident_analytics_honesty.py).
function formatSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s - h * 3600) / 60);
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[var(--radius-ui)] border border-border bg-panel px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function IncidentAnalytics() {
  const t = useT();
  const analytics = useIncidentAnalytics();
  const me = useMe();
  const canExport = can(me.data?.capabilities, "report:export");
  if (analytics.isPending) return <Loading rows={3} />;
  if (analytics.error) return <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />;
  const a = analytics.data!;
  const exportLink = canExport ? (
    <Button asChild variant="secondary" size="sm">
      <a href="/api/v1/incidents/export">{t("incidents.export")}</a>
    </Button>
  ) : null;
  if (a.total === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("incidents.analytics")}</CardTitle>
          {exportLink}
        </CardHeader>
        <CardContent>
          <Empty title={t("incidents.analytics.empty")} />
        </CardContent>
      </Card>
    );
  }
  // M2-R7: severityValues es la lista ordenada de las cuatro severidades
  // conocidas (sin "unknown"); severityOrder es el mapa de pesos de T22 y no
  // se itera aquí.
  const bySeverity = severityValues
    .map((s) => ({ name: t(`severity.${s}` as never), value: a.by_severity[s] ?? 0, tone: severityTone(s) }))
    .filter((row) => row.value > 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("incidents.analytics")}</CardTitle>
        {exportLink}
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Kpi label={t("incidents.analytics.total")} value={a.total} />
          <Kpi label={t("incident.status.open")} value={a.open} />
          <Kpi label={t("incident.status.ack")} value={a.ack} />
          <Kpi label={t("incident.status.closed")} value={a.closed} />
          <Kpi label={t("incidents.analytics.mttr")} value={a.mttr_seconds == null ? t("incidents.analytics.mttr.none") : formatSeconds(a.mttr_seconds)} />
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-fg-2">{t("incidents.analytics.byDay")}</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={a.by_day}>
                <XAxis dataKey="day" tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="var(--color-muted)" />
                <Tooltip />
                <Bar dataKey="count" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-fg-2">{t("incidents.analytics.bySeverity")}</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={bySeverity} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75}>
                  {bySeverity.map((row) => (
                    <Cell key={row.name} fill={toneColor[row.tone]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-2">
              {bySeverity.map((row) => (
                <li key={row.name} className="flex items-center gap-1.5">
                  <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: toneColor[row.tone] }} />
                  {row.name}: <span className="tabular-nums">{row.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-medium text-fg-2">{t("incidents.analytics.topDevices")}</p>
          <ul className="divide-y divide-border text-sm">
            {a.top_devices.map((d) => (
              <li key={d.device_id} className="flex justify-between py-1.5">
                <span>{d.device_name}</span>
                <span className="tabular-nums text-muted">{d.count}</span>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
