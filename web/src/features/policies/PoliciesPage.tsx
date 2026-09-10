import { useState } from "react";
import { Link } from "react-router";
import { Plus, Sparkle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/data-table/DataTable";
import { SeverityBadge } from "@/components/SeverityBadge";
import { ErrorState } from "@/components/states/ErrorState";
import { useMe, usePolicies, useUpdatePolicy, type Policy } from "@/api/hooks";
import { useT, type Key } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { describeCondition } from "./policyForm";

export function PoliciesPage() {
  const t = useT();
  const policies = usePolicies();
  const update = useUpdatePolicy();
  const me = useMe();
  const canWrite = can(me.data?.capabilities, "policy:write");
  const [toggling, setToggling] = useState("");
  // El estado vacío ya ofrece "Partir de una plantilla" como única acción del
  // hueco (mismo patrón de un solo CTA que `FencesPage`); repetirla en la
  // cabecera duplicaría el enlace en el DOM (dos "Partir de una plantilla"
  // con el mismo nombre accesible), así que la cabecera se oculta mientras
  // se sabe con certeza que la lista está vacía.
  const isEmpty = policies.data !== undefined && policies.data.items.length === 0;

  const templateLink = (
    <Button asChild variant="secondary">
      <Link to="/policies/new?plantillas=1">
        <Sparkle size={16} aria-hidden /> {t("policies.template")}
      </Link>
    </Button>
  );

  const columns: Column<Policy>[] = [
    {
      key: "name",
      header: t("policies.col.name"),
      cell: (p) => (
        <>
          <Link to={`/policies/${p.id}`} className="font-medium hover:text-accent">
            {p.name}
          </Link>
          <span className="ml-2 font-mono text-xs text-muted">{p.id}</span>
        </>
      ),
    },
    { key: "severity", header: t("policies.col.severity"), cell: (p) => <SeverityBadge severity={p.severity} /> },
    {
      key: "when",
      header: t("policies.col.when"),
      cell: (p) => <span className="text-fg-2">{p.when.map((c) => describeCondition(c, t)).join(t("policies.and"))}</span>,
    },
    {
      key: "actions",
      header: t("policies.col.actions"),
      cell: (p) => (p.actions.length === 0 ? t("policies.noActions") : p.actions.map((a) => t(`fence.action.${a.action}` as Key)).join(", ")),
    },
    {
      key: "enabled",
      header: t("policies.col.enabled"),
      cell: (p) => (
        <button
          type="button"
          role="switch"
          aria-checked={p.enabled}
          aria-label={t("policies.enabled.toggle", { name: p.name })}
          disabled={!canWrite || toggling === p.id}
          onClick={() => {
            setToggling(p.id);
            // PUT reemplaza el registro entero (T18): se envía la política tal
            // cual llegó con un único campo cambiado, sin reconstruir nada.
            update.mutate({ ...p, enabled: !p.enabled }, { onSettled: () => setToggling("") });
          }}
          className="rounded-full border border-border px-2 py-0.5 text-xs disabled:opacity-50"
        >
          {p.enabled ? t("common.yes") : t("common.no")}
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("policies.title")}</h1>
        {canWrite && !isEmpty && (
          <div className="flex gap-2">
            {templateLink}
            <Button asChild>
              <Link to="/policies/new">
                <Plus size={16} aria-hidden /> {t("policies.new")}
              </Link>
            </Button>
          </div>
        )}
      </div>
      {update.error && <ErrorState error={update.error} />}
      <DataTable
        columns={columns}
        rows={policies.data?.items}
        rowKey={(p) => p.id}
        loading={policies.isPending}
        error={policies.error}
        onRetry={() => policies.refetch()}
        empty={{ title: t("policies.empty"), action: canWrite ? templateLink : undefined }}
      />
    </div>
  );
}
