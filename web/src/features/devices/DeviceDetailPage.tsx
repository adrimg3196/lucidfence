import { Link, useParams } from "react-router";
import { ArrowLeft } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StateBadge } from "@/components/StateBadge";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { Empty } from "@/components/states/Empty";
import { useDevice, useDeviceTrail, useEvents, useIncidents, useMe } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { RiskExplain } from "./RiskExplain";
import { SignalsTable } from "./SignalsTable";
import { DeviceActions } from "./DeviceActions";

export function DeviceDetailPage() {
  const { id = "" } = useParams();
  const t = useT();
  const { lang } = useLang();
  const device = useDevice(id);
  const trail = useDeviceTrail(id, 20);
  const events = useEvents(200);
  const incidents = useIncidents({ device_id: id, status: "open" });
  const me = useMe();
  const canAct = can(me.data?.capabilities, "device:action");
  if (device.isPending) return <Loading rows={6} />;
  if (device.error) return <ErrorState error={device.error} onRetry={() => device.refetch()} />;
  const d = device.data!;
  const inv = d.inventory ?? {};
  const yesNo = (v: boolean | undefined) => (v == null ? t("common.unknown") : v ? t("common.yes") : t("common.no"));
  const fields: [string, string][] = [
    [t("device.field.os"), inv.os_version ?? "-"],
    [t("device.field.model"), inv.model ?? "-"],
    [t("device.field.serial"), inv.serial_number ?? "-"],
    [t("device.field.battery"), inv.battery_level != null ? `${inv.battery_level} %` : "-"],
    [t("device.field.storage"), inv.storage_total_gb != null ? `${inv.storage_free_gb ?? "?"} / ${inv.storage_total_gb} GB` : "-"],
    [t("device.field.encryption"), yesNo(inv.encryption_enabled)],
    [t("device.field.user"), inv.assigned_user ?? "-"],
    [t("device.field.department"), inv.department ?? "-"],
    [t("device.field.route"), d.route_id ? `${d.route_id} (${d.route_state})` : "-"],
  ];
  const mine = (events.data?.items ?? []).filter((e) => e.device_id === id).reverse();
  return (
    <div className="space-y-6">
      <Link to="/devices" className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> {t("device.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{d.name}</h1>
        <span className="font-mono text-sm text-muted">{d.id}</span>
        <span className="text-sm text-muted">{d.platform}</span>
        <StateBadge state={d.fence_state} />
        {d.inside_fence && <span className="text-sm text-muted">{d.inside_fence}</span>}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("device.inventory")}</CardTitle>
          </CardHeader>
          <CardContent>
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
            <CardTitle>{t("device.risk")}</CardTitle>
          </CardHeader>
          <CardContent>
            <RiskExplain verdict={d.risk} signals={d.signals} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("device.trail")}</CardTitle>
          </CardHeader>
          <CardContent>
            {trail.isPending && <Loading rows={3} />}
            {trail.error && <ErrorState error={trail.error} onRetry={() => trail.refetch()} />}
            {trail.data && trail.data.items.length === 0 && <Empty title={t("device.trail.empty")} />}
            {trail.data && trail.data.items.length > 0 && (
              <ul className="space-y-1 font-mono text-xs text-fg-2">
                {[...trail.data.items].reverse().map((p, i) => (
                  <li key={i}>
                    {formatDateTime(p.at, lang)} · {p.point.lat.toFixed(5)}, {p.point.lng.toFixed(5)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("device.events")}</CardTitle>
          </CardHeader>
          <CardContent>
            {events.isPending && <Loading rows={3} />}
            {events.error && <ErrorState error={events.error} onRetry={() => events.refetch()} />}
            {events.data && mine.length === 0 && <Empty title={t("device.events.empty")} />}
            {events.data && mine.length > 0 && (
              <ul className="divide-y divide-border text-sm">
                {mine.map((ev, i) => (
                  <li key={i} className="flex justify-between py-2">
                    <span>
                      <span className="text-muted">{ev.from}</span> → <span>{ev.to}</span>
                    </span>
                    <span className="text-muted">{formatDateTime(ev.at, lang)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>{t("risk.signals")}</CardTitle>
          </CardHeader>
          <CardContent>
            <SignalsTable signals={d.signals} />
          </CardContent>
        </Card>
        {canAct && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{t("device.actions")}</CardTitle>
            </CardHeader>
            <CardContent>
              <DeviceActions device={d} />
            </CardContent>
          </Card>
        )}
        <Card className={canAct ? "" : "lg:col-span-3"}>
          <CardHeader>
            <CardTitle>{t("device.incidents")}</CardTitle>
          </CardHeader>
          <CardContent>
            {incidents.isPending && <Loading rows={2} />}
            {incidents.error && <ErrorState error={incidents.error} onRetry={() => incidents.refetch()} />}
            {incidents.data && incidents.data.items.length === 0 && <Empty title={t("device.incidents.empty")} />}
            {incidents.data && incidents.data.items.length > 0 && (
              <ul className="divide-y divide-border text-sm">
                {incidents.data.items.map((inc) => (
                  <li key={inc.id} className="flex items-center justify-between py-2">
                    <Link to={`/incidents/${inc.id}`} className="font-medium hover:text-accent">
                      {inc.title}
                    </Link>
                    <span className="text-muted">{formatDateTime(inc.opened_at, lang)}</span>
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
