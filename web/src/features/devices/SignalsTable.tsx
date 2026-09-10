import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Empty } from "@/components/states/Empty";
import { useT } from "@/lib/i18n";

// Mismo orden que risk.Names en el motor (internal/domain/risk/signals.go, T2):
// siete señales estables, siempre en esta secuencia.
const SIGNAL_ORDER = ["time_of_day", "shift_match", "device_health", "device_posture", "location_integrity", "zone_risk", "route_state"] as const;

type Signals = { [name: string]: { [key: string]: unknown } | null };

// "Desconocido" y "falso" son cosas distintas en todo el producto (spec: los
// campos que el UEM no informa son nil, no cero). null/undefined es siempre
// "desconocido"; un booleano false real se lee "No", nunca "desconocido".
function formatValue(v: unknown, t: ReturnType<typeof useT>): string {
  if (v === null || v === undefined) return t("common.unknown");
  if (typeof v === "boolean") return v ? t("common.yes") : t("common.no");
  return String(v);
}

export function SignalsTable({ signals }: { signals?: Signals }) {
  const t = useT();
  const hasAny = SIGNAL_ORDER.some((name) => Object.keys(signals?.[name] ?? {}).length > 0);
  if (!hasAny) return <Empty title={t("risk.signals.empty")} />;
  const rows = SIGNAL_ORDER.flatMap((name) => {
    const entries = Object.entries(signals?.[name] ?? {});
    if (entries.length === 0) return [{ name, key: "-", value: "-" }];
    return entries.map(([key, value]) => ({ name, key, value: formatValue(value, t) }));
  });
  return (
    <Table>
      <THead>
        <tr>
          <TH>{t("risk.signals.col.signal")}</TH>
          <TH>{t("risk.signals.col.key")}</TH>
          <TH>{t("risk.signals.col.value")}</TH>
        </tr>
      </THead>
      <TBody>
        {rows.map((r, i) => (
          <TR key={`${r.name}-${r.key}-${i}`}>
            <TD>{t(`risk.signal.${r.name}`)}</TD>
            <TD className="font-mono text-xs text-muted">{r.key}</TD>
            <TD>{r.value}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
