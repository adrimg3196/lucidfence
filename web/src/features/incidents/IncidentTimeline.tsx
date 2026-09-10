import { ArrowRight } from "@phosphor-icons/react";
import { Empty } from "@/components/states/Empty";
import type { Incident } from "@/api/hooks";
import { useLang, useT } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

// El historial es la prueba de quién hizo qué: actor, transición, nota y sello
// de tiempo. `from` vacío es la apertura que escribe el motor.
export function IncidentTimeline({ entries }: { entries: Incident["timeline"] }) {
  const t = useT();
  const { lang } = useLang();
  if (entries.length === 0) return <Empty title={t("incident.timeline.empty")} />;
  return (
    <ol className="space-y-3 text-sm">
      {entries.map((e, i) => (
        <li key={`${e.at}-${i}`} className="border-l-2 border-border pl-3">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-fg">{e.actor}</span>
            <span className="inline-flex items-center gap-1 text-muted">
              {e.from ? t(`incident.status.${e.from}` as never) : "-"}
              <ArrowRight size={12} aria-hidden />
              {t(`incident.status.${e.to}` as never)}
            </span>
            <span className="text-xs text-muted">{formatDateTime(e.at, lang)}</span>
          </p>
          {e.note && <p className="mt-0.5 text-fg-2">{e.note}</p>}
        </li>
      ))}
    </ol>
  );
}
