import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices, useEngineStatus, useEvents } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime, percent } from "@/lib/format";
import { Kpi } from "./Kpi";
import { EngineCard } from "./EngineCard";

export function OverviewPage() {
  const t = useT();
  const { lang } = useLang();
  const devices = useDevices();
  const events = useEvents(10);
  const engine = useEngineStatus();
  const items = devices.data?.items ?? [];
  const count = (s: string) => items.filter((d) => d.fence_state === s).length;
  const compliant = items.filter((d) => d.compliant === true).length;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("overview.title")}</h1>
      {devices.isPending && <Loading rows={2} />}
      {devices.error && <ErrorState error={devices.error} onRetry={() => devices.refetch()} />}
      {devices.data && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <Kpi label={t("overview.devices")} value={items.length} />
          <Kpi label={t("overview.inside")} value={count("inside")} tone="success" />
          <Kpi label={t("overview.outside")} value={count("outside")} tone="warning" />
          <Kpi label={t("overview.unknown")} value={count("unknown")} />
          <Kpi label={t("overview.compliance")} value={percent(compliant, items.length)} />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-6">
          <EngineCard />
          <Card>
            <CardHeader>
              <CardTitle>{t("overview.providers")}</CardTitle>
            </CardHeader>
            <CardContent>
              {engine.data && (
                <ul className="divide-y divide-border text-sm">
                  {Object.entries(engine.data.providers).map(([name, h]) => (
                    <li key={name} className="flex items-center justify-between py-2">
                      <span>{name}</span>
                      <span className="flex items-center gap-2 text-muted">
                        {h.devices} · {h.latency_ms} ms
                        <Badge variant={h.ok ? "success" : "danger"}>{h.ok ? "ok" : h.error}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{t("overview.events")}</CardTitle>
          </CardHeader>
          <CardContent>
            {events.isPending && <Loading rows={4} />}
            {events.error && <ErrorState error={events.error} onRetry={() => events.refetch()} />}
            {events.data && events.data.items.length === 0 && <Empty title={t("overview.noEvents")} />}
            {events.data && events.data.items.length > 0 && (
              <ul className="divide-y divide-border text-sm">
                {[...events.data.items].reverse().map((ev, i) => (
                  <li key={i} className="grid grid-cols-[1fr_auto] gap-2 py-2">
                    <span>
                      <span className="font-medium">{ev.device_name}</span> <span className="text-muted">{ev.from}</span> → <span>{ev.to}</span>
                    </span>
                    <span className="text-muted">{formatDateTime(ev.at, lang)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
