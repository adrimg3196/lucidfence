import { Link, useParams } from "react-router";
import { ArrowLeft } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StateBadge } from "@/components/StateBadge";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevice, useDeviceTrail, useEvents } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

export function DeviceDetailPage() {
  const { id = "" } = useParams();
  const t = useT();
  const { lang } = useLang();
  const device = useDevice(id);
  const trail = useDeviceTrail(id, 20);
  const events = useEvents(200);
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
            <p className="text-sm text-muted">{d.risk?.score == null ? t("device.risk.pending") : `${d.risk.score} · ${d.risk.severity}`}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("device.trail")}</CardTitle>
          </CardHeader>
          <CardContent>
            {trail.isPending && <Loading rows={3} />}
            {trail.data && (
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
            {events.data && (
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
      </div>
    </div>
  );
}
