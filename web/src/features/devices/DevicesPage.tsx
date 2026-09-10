import { useState } from "react";
import { Link } from "react-router";
import { MagnifyingGlass, CaretUp, CaretDown } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NativeSelect } from "@/components/ui/select";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { StateBadge } from "@/components/StateBadge";
import { RiskScore } from "@/components/RiskScore";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

const states = ["", "inside", "outside", "unknown"] as const;
const severities = ["", "low", "medium", "high", "critical", "unknown"] as const;

export function DevicesPage() {
  const t = useT();
  const { lang } = useLang();
  const [state, setState] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");
  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 250);
  const [riskSort, setRiskSort] = useState<"asc" | "desc" | null>(null);
  const devices = useDevices({ state, q: debouncedQ, severity });
  const items = devices.data?.items ?? [];
  // Un dispositivo sin veredicto se queda siempre al final, en cualquiera de
  // los dos sentidos: nunca se confunde con el riesgo más bajo posible.
  const rows = riskSort
    ? [...items].sort((a, b) => {
        const av = a.risk?.score ?? (riskSort === "asc" ? Infinity : -Infinity);
        const bv = b.risk?.score ?? (riskSort === "asc" ? Infinity : -Infinity);
        return riskSort === "asc" ? av - bv : bv - av;
      })
    : items;
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
        <div className="flex gap-3">
          <NativeSelect aria-label={t("risk.filter.severity")} value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-44">
            {severities.map((s) => (
              <option key={s} value={s}>
                {s === "" ? t("devices.filter.severityAll") : t(`risk.severity.${s}`)}
              </option>
            ))}
          </NativeSelect>
          <div className="relative md:w-80">
            <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-2.5 text-muted" aria-hidden />
            <Input type="search" role="searchbox" placeholder={t("devices.search")} value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
          </div>
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
              <TH>
                <button type="button" className="inline-flex items-center gap-1" onClick={() => setRiskSort((s) => (s === "asc" ? "desc" : "asc"))}>
                  {t("devices.col.risk")}
                  {riskSort === "asc" && <CaretUp size={12} aria-hidden />}
                  {riskSort === "desc" && <CaretDown size={12} aria-hidden />}
                </button>
              </TH>
              <TH>{t("devices.col.user")}</TH>
              <TH>{t("devices.col.lastReport")}</TH>
            </tr>
          </THead>
          <TBody>
            {rows.map((d) => (
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
                <TD>
                  <RiskScore score={d.risk?.score ?? null} severity={d.risk?.severity ?? "unknown"} />
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
