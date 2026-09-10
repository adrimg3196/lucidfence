import { useState } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable, type Column } from "@/components/data-table/DataTable";
import { SeverityBadge } from "@/components/SeverityBadge";
import { useDevices, useIncidents, useMe, usePatchIncident, useRunOnce, type Incident } from "@/api/hooks";
import { useLang, useT } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { IncidentAnalytics } from "./IncidentAnalytics";

// La bandeja arranca en "abiertos": lo que hay que triar hoy, no el archivo.
const tabs = [
  { value: "open", key: "incidents.tab.open" },
  { value: "ack", key: "incidents.tab.ack" },
  { value: "closed", key: "incidents.tab.closed" },
  { value: "", key: "incidents.tab.all" },
] as const;

const statusVariant = { open: "danger", ack: "warning", closed: "neutral" } as const;

export function IncidentsPage() {
  const t = useT();
  const { lang } = useLang();
  const [status, setStatus] = useState<string>("open");
  const [deviceID, setDeviceID] = useState<string>("");
  const incidents = useIncidents({ status: status || undefined, device_id: deviceID || undefined });
  const devices = useDevices();
  const patch = usePatchIncident();
  const runOnce = useRunOnce();
  const me = useMe();
  const canWrite = can(me.data?.capabilities, "incident:write");
  const canRun = can(me.data?.capabilities, "engine:run");

  const columns: Column<Incident>[] = [
    { key: "severity", header: t("incidents.col.severity"), cell: (i) => <SeverityBadge severity={i.severity} /> },
    {
      key: "title",
      header: t("incidents.col.title"),
      cell: (i) => (
        <>
          <Link to={`/incidents/${i.id}`} className="font-medium text-fg hover:text-accent">
            {i.title}
          </Link>
          <span className="ml-2 font-mono text-xs text-muted">{i.kind}</span>
        </>
      ),
    },
    {
      key: "device",
      header: t("incidents.col.device"),
      cell: (i) => (
        <Link to={`/devices/${i.device_id}`} className="hover:text-accent">
          {i.device_name}
        </Link>
      ),
    },
    { key: "status", header: t("incidents.col.status"), cell: (i) => <Badge variant={statusVariant[i.status]}>{t(`incident.status.${i.status}` as never)}</Badge> },
    { key: "count", header: t("incidents.col.count"), cell: (i) => i.count },
    { key: "opened", header: t("incidents.col.opened"), className: "text-muted", cell: (i) => formatDateTime(i.opened_at, lang) },
    {
      key: "actions",
      header: t("incidents.col.actions"),
      className: "text-right",
      cell: (i) =>
        canWrite && i.status === "open" ? (
          // usePatchIncident (T22) manda { id, patch: IncidentPatch }, no el
          // status suelto: ver "Desviaciones" del informe de esta tarea.
          <Button variant="ghost" size="sm" disabled={patch.isPending} onClick={() => patch.mutate({ id: i.id, patch: { status: "ack" } })}>
            {t("incident.ack")}
          </Button>
        ) : null,
    },
  ];

  const runButton = canRun ? (
    <Button onClick={() => runOnce.mutate()} disabled={runOnce.isPending}>
      {t(runOnce.isPending ? "overview.engine.running" : "overview.engine.run")}
    </Button>
  ) : undefined;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("incidents.title")}</h1>
      <IncidentAnalytics />
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList>
            {tabs.map((tab) => (
              <TabsTrigger key={tab.value || "all"} value={tab.value}>
                {t(tab.key)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="space-y-1.5 md:w-72">
          <Label htmlFor="device-filter">{t("incidents.filter.device")}</Label>
          <NativeSelect id="device-filter" value={deviceID} onChange={(e) => setDeviceID(e.target.value)}>
            <option value="">{t("incidents.filter.device.all")}</option>
            {(devices.data?.items ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>
      <DataTable
        columns={columns}
        rows={incidents.data?.items}
        rowKey={(i) => i.id}
        loading={incidents.isPending}
        error={incidents.error}
        onRetry={() => incidents.refetch()}
        empty={{ title: t("incidents.empty"), description: t("incidents.empty.help"), action: runButton }}
      />
    </div>
  );
}
