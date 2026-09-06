import { useState } from "react";
import { Link } from "react-router";
import { Plus } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDeleteFence, useFences, useMe, type Fence } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

export function FencesPage() {
  const t = useT();
  const fences = useFences();
  const del = useDeleteFence();
  const me = useMe();
  const [pending, setPending] = useState<Fence | null>(null);
  const canWrite = can(me.data?.capabilities, "fence:write");
  const canDelete = can(me.data?.capabilities, "fence:delete");
  const newButton = canWrite && (
    <Button asChild>
      <Link to="/fences/new">
        <Plus size={16} aria-hidden /> {t("fences.new")}
      </Link>
    </Button>
  );
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("fences.title")}</h1>
        {newButton}
      </div>
      {fences.isPending && <Loading rows={4} />}
      {fences.error && <ErrorState error={fences.error} onRetry={() => fences.refetch()} />}
      {fences.data && fences.data.items.length === 0 && <Empty title={t("fences.empty")} action={newButton || undefined} />}
      {fences.data && fences.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("fences.col.name")}</TH>
              <TH>{t("fences.col.kind")}</TH>
              <TH>{t("fences.col.actions")}</TH>
              <TH />
            </tr>
          </THead>
          <TBody>
            {fences.data.items.map((f) => (
              <TR key={f.id}>
                <TD>
                  <Link to={`/fences/${f.id}`} className="font-medium hover:text-accent">
                    {f.name}
                  </Link>
                  <span className="ml-2 font-mono text-xs text-muted">{f.id}</span>
                </TD>
                <TD>{t(`fence.kind.${f.kind}`)}</TD>
                <TD>{f.actions.length}</TD>
                <TD className="text-right">
                  {canDelete && (
                    <Button variant="ghost" size="sm" onClick={() => setPending(f)}>
                      {t("fences.delete")}
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={t("fences.delete")}
        description={pending ? t("fences.delete.confirm", { name: pending.name }) : undefined}
        confirmLabel={t("fences.delete")}
        cancelLabel={t("fence.cancel")}
        onConfirm={() => {
          if (pending) del.mutate(pending.id);
          setPending(null);
        }}
      />
    </div>
  );
}
