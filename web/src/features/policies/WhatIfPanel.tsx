import { Play } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { SeverityBadge } from "@/components/SeverityBadge";
import { useReplayPolicy, type Policy } from "@/api/hooks";
import { useLang, useT } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-ui)] border border-border p-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

export function WhatIfPanel({ policy, onRun }: { policy: Policy; onRun?: () => void }) {
  const t = useT();
  const { lang } = useLang();
  const replay = useReplayPolicy();
  const r = replay.data;
  return (
    <section className="space-y-3 rounded-[var(--radius-ui)] border border-border p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("policy.whatif.title")}</h2>
        <Button
          type="button"
          variant="secondary"
          disabled={replay.isPending}
          // La política viaja en el cuerpo y no necesita existir (T18): se
          // simula lo que hay en el formulario, guardado o no.
          onClick={() => replay.mutate({ policy, use_current_fences: true }, { onSuccess: () => onRun?.() })}
        >
          <Play size={16} aria-hidden /> {replay.isPending ? t("policy.whatif.running") : t("policy.whatif.run")}
        </Button>
      </div>
      <p className="text-sm text-muted">{t("policy.whatif.help")}</p>
      {replay.error && <ErrorState error={replay.error} />}
      {r && r.approximation && <p className="text-sm text-sev-medium">{t("policy.whatif.approximation")}</p>}
      {r && r.notes.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {r.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {r && r.firings === 0 && <Empty title={t("policy.whatif.empty")} description={t("policy.whatif.empty.help", { points: r.points_evaluated })} />}
      {r && r.firings > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            <Metric label={t("policy.whatif.firings")} value={String(r.firings)} />
            <Metric label={t("policy.whatif.devices")} value={`${Object.keys(r.by_device).length} / ${r.devices_evaluated}`} />
            <Metric label={t("policy.whatif.points")} value={String(r.points_evaluated)} />
            <Metric label={t("policy.whatif.window")} value={`${formatDateTime(r.from, lang)} - ${formatDateTime(r.to, lang)}`} />
          </div>
          <p className="text-sm text-fg-2">
            {t("policy.whatif.byAction")}:{" "}
            {Object.entries(r.by_action)
              .map(([a, n]) => `${a}: ${n}`)
              .join(" · ")}
          </p>
          <Table>
            <THead>
              <tr>
                <TH>{t("policy.whatif.samples")}</TH>
                <TH>{t("policies.col.severity")}</TH>
                <TH>{t("policy.whatif.reasons")}</TH>
              </tr>
            </THead>
            <TBody>
              {r.samples.map((s, i) => (
                <TR key={`${s.device_id}-${s.at}-${i}`}>
                  <TD>
                    <span className="font-medium">{s.device_name}</span>
                    <span className="ml-2 text-xs text-muted">{formatDateTime(s.at, lang)}</span>
                  </TD>
                  <TD>
                    <SeverityBadge severity={s.severity} />
                    {s.score != null && <span className="ml-2 text-xs text-muted">{s.score}</span>}
                  </TD>
                  <TD className="text-fg-2">{s.reasons.join(" · ")}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </>
      )}
    </section>
  );
}
