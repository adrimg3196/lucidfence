import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/states/ErrorState";
import type { Handoff } from "@/api/hooks";
import { useT } from "@/lib/i18n";

export type Decision = "approve" | "reject";

// DecisionDialog es la fricción deliberada antes de una orden irreversible: la
// nota es obligatoria en las dos decisiones y, si la acción es un wipe, hay que
// teclear el identificador del dispositivo. Es la versión con manos de
// 1.x static/app.js ("BORRADO IRREVERSIBLE de <id>"), que se despachaba con un
// confirm() del navegador.
export function DecisionDialog({ open, decision, handoff, pending, error, onOpenChange, onConfirm }: {
  open: boolean;
  decision: Decision;
  handoff: Handoff;
  pending: boolean;
  error: unknown;
  onOpenChange: (o: boolean) => void;
  onConfirm: (note: string) => void;
}) {
  const t = useT();
  // HandoffsPage solo monta este diálogo mientras hay una pregunta pendiente
  // (`{asked && <DecisionDialog .../>}`) y lo desmonta al cancelar o al
  // decidir: cada apertura es un montaje nuevo, así que el estado inicial ya
  // empieza en blanco sin necesitar un efecto que lo reponga.
  const [note, setNote] = useState("");
  const [typed, setTyped] = useState("");
  const action = t(`fence.action.${handoff.action}`);
  const needsID = decision === "approve" && handoff.action === "wipe";
  const ready = note.trim().length > 0 && (!needsID || typed.trim() === handoff.device_id);
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t(decision === "approve" ? "handoff.dialog.approve.title" : "handoff.dialog.reject.title", { action })}
      description={t("handoff.dialog.summary", { action, device: handoff.device_name, id: handoff.device_id, playbook: handoff.playbook_name })}
      confirmLabel={t(decision === "approve" ? "handoff.approve" : "handoff.reject")}
      cancelLabel={t("handoff.dialog.cancel")}
      confirmDisabled={!ready || pending}
      onConfirm={() => onConfirm(note.trim())}
    >
      <div className="mt-4 space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="handoff-note">{t("handoff.dialog.note")}</Label>
          <textarea
            id="handoff-note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded-[var(--radius-ui)] border border-border bg-panel p-2 text-sm"
          />
          <p className="text-xs text-muted">{t("handoff.dialog.note.help")}</p>
        </div>
        {needsID && (
          <div className="space-y-1.5">
            <p className="text-sm text-sev-high">{t("handoff.dialog.irreversible")}</p>
            <Label htmlFor="handoff-confirm-id">{t("handoff.dialog.confirmId", { id: handoff.device_id })}</Label>
            <Input id="handoff-confirm-id" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
          </div>
        )}
        {/* El fondo queda aria-hidden mientras el diálogo está abierto (M1-R27,
            C13): el error de la decisión tiene que verse aquí dentro. */}
        {error != null && <ErrorState error={error} />}
      </div>
    </ConfirmDialog>
  );
}
