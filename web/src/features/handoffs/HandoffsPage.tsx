import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { ApiError } from "@/api/client";
import { useApproveHandoff, useHandoffs, useMe, useRejectHandoff, type Handoff } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { HandoffCard } from "./HandoffCard";
import { DecisionDialog, type Decision } from "./DecisionDialog";

const statuses = ["pending", "approved", "rejected", "executed", ""] as const;

export function HandoffsPage() {
  const t = useT();
  // La bandeja se abre para decidir, no para leer historia: arranca en pending.
  const [status, setStatus] = useState<string>("pending");
  const handoffs = useHandoffs(status || undefined);
  const me = useMe();
  const approve = useApproveHandoff();
  const reject = useRejectHandoff();
  const [asked, setAsked] = useState<{ handoff: Handoff; decision: Decision } | null>(null);
  // decided guarda el handoff que devolvió la mutación (T20: la respuesta lleva
  // el resultado dentro) para enseñarlo sin esperar al refetch de la lista.
  const [decided, setDecided] = useState<Record<string, Handoff>>({});
  const [conflict, setConflict] = useState(false);
  const canDecide = can(me.data?.capabilities, "handoff:approve");
  const mutation = asked?.decision === "reject" ? reject : approve;

  const confirm = (note: string) => {
    if (!asked) return;
    const id = asked.handoff.id;
    setConflict(false);
    mutation.mutate(
      { id, note },
      {
        onSuccess: (h: Handoff) => {
          setDecided((prev) => ({ ...prev, [id]: h }));
          setAsked(null);
        },
        onError: (e: unknown) => {
          // 409: otro operador decidió antes. No es un fallo del sistema, es una
          // carrera; se avisa y se recarga en vez de dejar la tarjeta obsoleta.
          if (e instanceof ApiError && e.status === 409) {
            setConflict(true);
            setAsked(null);
            handoffs.refetch();
          }
        },
      },
    );
  };

  const items = (handoffs.data?.items ?? []).map((h) => decided[h.id] ?? h);
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">{t("handoffs.title")}</h1>
      <Tabs value={status} onValueChange={setStatus}>
        <TabsList>
          {statuses.map((s) => (
            <TabsTrigger key={s} value={s}>
              {s === "" ? t("handoffs.filter.all") : t(`handoff.status.${s}`)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {conflict && (
        <p role="status" className="rounded-[var(--radius-ui)] border border-sev-medium/30 bg-sev-medium/5 p-3 text-sm text-fg-2">
          {t("handoff.conflict")}
        </p>
      )}
      {handoffs.isPending && <Loading rows={3} />}
      {handoffs.error && <ErrorState error={handoffs.error} onRetry={() => handoffs.refetch()} />}
      {handoffs.data && items.length === 0 && <Empty title={t("handoffs.empty")} />}
      {items.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((h) => {
            const decidable = canDecide && h.status === "pending";
            return (
              <HandoffCard
                key={h.id}
                handoff={h}
                onApprove={decidable ? () => setAsked({ handoff: h, decision: "approve" }) : undefined}
                onReject={decidable ? () => setAsked({ handoff: h, decision: "reject" }) : undefined}
              />
            );
          })}
        </div>
      )}
      {asked && (
        <DecisionDialog
          open
          decision={asked.decision}
          handoff={asked.handoff}
          pending={mutation.isPending}
          error={mutation.error}
          onOpenChange={(o) => !o && setAsked(null)}
          onConfirm={confirm}
        />
      )}
    </div>
  );
}
