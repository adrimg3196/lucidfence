import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/data-table/DataTable";
import { useEventsPage, type Transition } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

// La lista acumulada vive en estado local: useEventsPage solo conoce una
// página por llamada (T22). appliedCursor recuerda el último cursor ya
// volcado a `items`; sin él, el placeholderData de T22 (que enseña la página
// anterior mientras llega la siguiente) haría que este efecto concatenara la
// página vieja consigo misma en cuanto cambia el cursor.
//
// M2-R62: el centinela es `null`, no `undefined`. El cursor inicial también
// es `undefined` (primera página), así que si el ref arrancara en `undefined`
// la guarda dispararía en el primer render y la primera página nunca se
// volcaría. `next_cursor: ""` significa siempre "no hay más" y nunca se pasa
// como cursor, así que la cadena vacía es segura como representación de
// "primera página ya aplicada".
export function EventsPage() {
  const t = useT();
  const { lang } = useLang();
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<Transition[]>([]);
  const appliedCursor = useRef<string | null>(null);
  const page = useEventsPage(cursor);

  useEffect(() => {
    if (!page.data || page.isFetching) return;
    if (appliedCursor.current === (cursor ?? "")) return;
    appliedCursor.current = cursor ?? "";
    setItems((prev) => (cursor ? [...prev, ...page.data!.items] : page.data!.items));
  }, [page.data, page.isFetching, cursor]);

  const columns: Column<Transition>[] = [
    { key: "at", header: t("event.col.at"), cell: (e) => formatDateTime(e.at, lang) },
    {
      key: "device",
      header: t("event.col.device"),
      cell: (e) => (
        <Link to={`/devices/${e.device_id}`} className="hover:text-accent">
          {e.device_name}
        </Link>
      ),
    },
    { key: "from", header: t("event.col.from"), cell: (e) => e.from },
    { key: "to", header: t("event.col.to"), cell: (e) => e.to },
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
        <h1 className="text-2xl font-semibold tracking-tight">{t("event.title")}</h1>
        {cursor !== undefined && (
          <Button variant="ghost" size="sm" onClick={resetToFirst}>
            {t("event.first")}
          </Button>
        )}
      </div>
      <DataTable
        columns={columns}
        rows={items}
        rowKey={(e) => `${e.device_id}|${e.at}|${e.to}`}
        empty={{ title: t("event.empty") }}
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
