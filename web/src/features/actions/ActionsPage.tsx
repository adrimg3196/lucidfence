import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/SeverityBadge";
import { DataTable, type Column } from "@/components/data-table/DataTable";
import { useActionsPage, type ActionResult } from "@/api/hooks";
import { useT, useLang, type Key } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

// El motor sigue usando on_enter/on_exit/on_violation/on_unknown para las
// acciones de geocerca (M1, internal/engine/actions.go, sin cambios) y suma
// policy/route_exit/dwell en este hito (T14); ExecuteManual (T16) deja
// manual/handoff. T22 solo cerró siete claves action.trigger.*: los cuatro
// sabores de transición de geocerca comparten "transition" y la violación
// sostenida es la única que tiene bucket propio ("standing").
const triggerKeys: Record<string, Key> = {
  on_enter: "action.trigger.transition",
  on_exit: "action.trigger.transition",
  on_unknown: "action.trigger.transition",
  on_violation: "action.trigger.standing",
  policy: "action.trigger.policy",
  route_exit: "action.trigger.route_exit",
  dwell: "action.trigger.dwell",
  manual: "action.trigger.manual",
  handoff: "action.trigger.handoff",
};

function triggerKey(trigger: string | undefined): Key {
  return triggerKeys[trigger ?? ""] ?? "action.trigger.transition";
}

// El orden importa: un bloqueo del guardarraíl (una buena noticia: el
// guardarraíl hizo su trabajo) se distingue de un fallo real del conector, y
// ninguno de los dos se anuncia nunca como "ejecutada" si dry_run es true.
function resultKey(a: ActionResult): Key {
  if (a.blocked) return "action.blocked";
  if (!a.ok) return "action.failed";
  if (a.dry_run) return "action.dryRun";
  return "action.ok";
}

const resultVariant: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  "action.blocked": "warning",
  "action.failed": "danger",
  "action.dryRun": "neutral",
  "action.ok": "success",
};

function TriggerCell({ a }: { a: ActionResult }) {
  const t = useT();
  const label = t(triggerKey(a.trigger));
  // route_id no tiene página de detalle en este hito (ninguna tarea de M1-M2
  // publica una vista de rutas): se enseña como dato, no como enlace.
  if (a.policy_id) {
    return (
      <Link to={`/policies/${a.policy_id}`} className="hover:text-accent">
        {label} · {a.policy_id}
      </Link>
    );
  }
  if (a.playbook_id) {
    return (
      <Link to={`/playbooks/${a.playbook_id}`} className="hover:text-accent">
        {label} · {a.playbook_id}
      </Link>
    );
  }
  if (a.route_id) {
    return (
      <span>
        {label} · <span className="font-mono text-xs text-muted">{a.route_id}</span>
      </span>
    );
  }
  if (a.fence_id) {
    return (
      <Link to={`/fences/${a.fence_id}`} className="hover:text-accent">
        {label} · {a.fence_id}
      </Link>
    );
  }
  return <span>{label}</span>;
}

// El motivo de un bloqueo es el texto que ya llega en español desde el
// guardarraíl (ActionResult.Error, T12): no se vuelve a traducir en el
// cliente, igual que ErrorState hace desde M1 con ApiError.message.
// error_type (el código de máquina, p. ej. "wipe_not_allowed") se enseña
// aparte, en monoespaciada, como dato técnico, en su propio nodo de texto:
// concatenarlo en la misma cadena que `adapter` deja "wipe_not_allowed" sin
// un elemento propio cuyo texto exacto sea ese código, que es justo lo que
// necesita quien lo busca (el registro de acciones, para investigar un
// bloqueo).
function ResultCell({ a }: { a: ActionResult }) {
  const t = useT();
  const key = resultKey(a);
  return (
    <div className="space-y-1">
      <Badge variant={resultVariant[key]}>{t(key)}</Badge>
      {a.error && <p className={a.blocked ? "text-xs text-sev-medium" : "text-xs text-sev-high"}>{a.error}</p>}
      <p className="text-xs text-muted">
        {a.adapter}
        {a.error_type && (
          <>
            {" · "}
            <span className="font-mono">{a.error_type}</span>
          </>
        )}
      </p>
    </div>
  );
}

// M2-R62: mismo centinela `null` que EventsPage, misma razón (el `undefined`
// inicial del ref coincidía con el `cursor` inicial y la primera página no
// se volcaba nunca).
export function ActionsPage() {
  const t = useT();
  const { lang } = useLang();
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<ActionResult[]>([]);
  const appliedCursor = useRef<string | null>(null);
  const page = useActionsPage(cursor);

  useEffect(() => {
    if (!page.data || page.isFetching) return;
    if (appliedCursor.current === (cursor ?? "")) return;
    appliedCursor.current = cursor ?? "";
    setItems((prev) => (cursor ? [...prev, ...page.data!.items] : page.data!.items));
  }, [page.data, page.isFetching, cursor]);

  const columns: Column<ActionResult>[] = [
    { key: "at", header: t("action.col.at"), cell: (a) => formatDateTime(a.at, lang) },
    {
      key: "device",
      header: t("action.col.device"),
      cell: (a) => (
        <Link to={`/devices/${a.device_id}`} className="hover:text-accent">
          {a.device_name}
        </Link>
      ),
    },
    {
      key: "action",
      header: t("action.col.action"),
      cell: (a) => (
        <span className="flex items-center gap-2">
          {t(`fence.action.${a.action}` as Key)}
          {a.severity && <SeverityBadge severity={a.severity} />}
        </span>
      ),
    },
    { key: "trigger", header: t("action.col.trigger"), cell: (a) => <TriggerCell a={a} /> },
    { key: "result", header: t("action.col.result"), cell: (a) => <ResultCell a={a} /> },
  ];

  const nextCursor = page.data?.next_cursor ?? "";
  const showMore = items.length > 0 && !page.error && nextCursor !== "";
  const resetToFirst = () => {
    appliedCursor.current = null;
    setItems([]);
    setCursor(undefined);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("action.title")}</h1>
        {cursor !== undefined && (
          <Button variant="ghost" size="sm" onClick={resetToFirst}>
            {t("event.first")}
          </Button>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={items}
        rowKey={(a) => `${a.device_id}|${a.at}|${a.action}|${a.trigger ?? ""}`}
        empty={{ title: t("action.empty") }}
        loading={page.isPending}
        error={page.error}
        onRetry={() => page.refetch()}
      />
      {showMore && (
        <div className="flex justify-center">
          <Button variant="secondary" onClick={() => setCursor(nextCursor)} disabled={page.isFetching}>
            {t("event.more")}
          </Button>
        </div>
      )}
    </div>
  );
}
