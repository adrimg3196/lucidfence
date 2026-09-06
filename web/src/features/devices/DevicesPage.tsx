import { useState } from "react";
import { Link } from "react-router";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { StateBadge } from "@/components/StateBadge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

const states = ["", "inside", "outside", "unknown"] as const;

export function DevicesPage() {
  const t = useT();
  const { lang } = useLang();
  const [state, setState] = useState<string>("");
  const [q, setQ] = useState("");
  const devices = useDevices({ state, q });
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">{t("devices.title")}</h1>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={state} onValueChange={setState}>
          <TabsList>
            {states.map((s) => (
              <TabsTrigger key={s} value={s}>
                {s === "" ? t("devices.filter.all") : t(`state.${s}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative md:w-80">
          <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-2.5 text-muted" aria-hidden />
          <Input type="search" role="searchbox" placeholder={t("devices.search")} value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
      </div>
      {devices.isPending && <Loading rows={6} />}
      {devices.error && <ErrorState error={devices.error} onRetry={() => devices.refetch()} />}
      {devices.data && devices.data.items.length === 0 && <Empty title={t("devices.empty")} />}
      {devices.data && devices.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("devices.col.name")}</TH>
              <TH>{t("devices.col.platform")}</TH>
              <TH>{t("devices.col.state")}</TH>
              <TH>{t("devices.col.user")}</TH>
              <TH>{t("devices.col.lastReport")}</TH>
            </tr>
          </THead>
          <TBody>
            {devices.data.items.map((d) => (
              <TR key={d.id}>
                <TD>
                  <Link to={`/devices/${d.id}`} className="font-medium text-fg hover:text-accent">
                    {d.name}
                  </Link>
                  <span className="ml-2 font-mono text-xs text-muted">{d.id}</span>
                </TD>
                <TD>{d.platform}</TD>
                <TD>
                  <StateBadge state={d.fence_state} />
                  {d.inside_fence && <span className="ml-2 text-xs text-muted">{d.inside_fence}</span>}
                </TD>
                <TD>{d.inventory?.assigned_user ?? "-"}</TD>
                <TD className="text-muted">{formatDateTime(d.last_report_at, lang)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
