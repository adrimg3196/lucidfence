import { useState } from "react";
import { Link } from "react-router";
import { Plus } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDeletePlaybook, useMe, usePlaybooks, type Playbook } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { destructiveIn } from "./playbookForm";

export function PlaybooksPage() {
  const t = useT();
  const playbooks = usePlaybooks();
  const del = useDeletePlaybook();
  const me = useMe();
  const [pending, setPending] = useState<Playbook | null>(null);
  const canWrite = can(me.data?.capabilities, "playbook:write");
  const newButton = canWrite && (
    <Button asChild>
      <Link to="/playbooks/new">
        <Plus size={16} aria-hidden /> {t("playbooks.new")}
      </Link>
    </Button>
  );
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("playbooks.title")}</h1>
        {newButton}
      </div>
      {playbooks.isPending && <Loading rows={4} />}
      {playbooks.error && <ErrorState error={playbooks.error} onRetry={() => playbooks.refetch()} />}
      {playbooks.data && playbooks.data.items.length === 0 && <Empty title={t("playbooks.empty")} action={newButton || undefined} />}
      {playbooks.data && playbooks.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("playbooks.col.name")}</TH>
              <TH>{t("playbooks.col.severity")}</TH>
              <TH>{t("playbooks.col.when")}</TH>
              <TH>{t("playbooks.col.actions")}</TH>
              <TH>{t("playbooks.col.state")}</TH>
              <TH />
            </tr>
          </THead>
          <TBody>
            {playbooks.data.items.map((p) => {
              const gated = destructiveIn(p.actions);
              return (
                <TR key={p.id}>
                  <TD>
                    <Link to={`/playbooks/${p.id}`} className="font-medium hover:text-accent">
                      {p.name}
                    </Link>
                    <span className="ml-2 font-mono text-xs text-muted">{p.id}</span>
                    {p.description && <p className="mt-0.5 text-xs text-muted">{p.description}</p>}
                  </TD>
                  <TD>
                    <SeverityBadge severity={p.severity} />
                  </TD>
                  <TD>{p.when.length}</TD>
                  <TD>
                    {p.actions.map((a) => (
                      <span key={a.action} className="mr-2 text-xs">
                        {t(`fence.action.${a.action}`)}
                      </span>
                    ))}
                    {/* Herencia de 1.x (static/app.js, loadSoar): la acción
                        destructiva se marca en la propia lista, no solo en el
                        editor. */}
                    {gated.length > 0 && <Badge variant="warning">{t("playbook.humanGate")}</Badge>}
                  </TD>
                  <TD>{p.enabled ? t("playbook.enabled") : t("playbook.disabled")}</TD>
                  <TD className="text-right">
                    {canWrite && (
                      <Button variant="ghost" size="sm" onClick={() => setPending(p)}>
                        {t("playbooks.delete")}
                      </Button>
                    )}
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={t("playbooks.delete")}
        description={pending ? t("playbooks.delete.confirm", { name: pending.name }) : undefined}
        confirmLabel={t("playbooks.delete")}
        cancelLabel={t("playbook.cancel")}
        confirmDisabled={del.isPending}
        onConfirm={() => {
          if (pending) del.mutate(pending.id, { onSuccess: () => setPending(null) });
        }}
      >
        {del.error && <ErrorState error={del.error} />}
      </ConfirmDialog>
    </div>
  );
}
