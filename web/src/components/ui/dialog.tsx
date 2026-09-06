import { Dialog as D } from "radix-ui";
import type { ReactNode } from "react";

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, cancelLabel, onConfirm, confirmDisabled, children }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  // M1-R27 (C13): deshabilita el botón de confirmar mientras la acción que
  // dispara está en curso (p. ej. useDeleteFence().isPending), para que no
  // se pueda disparar dos veces mientras se espera la respuesta del servidor.
  confirmDisabled?: boolean;
  children?: ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-fg/40" />
        <D.Content className="fixed left-1/2 top-1/2 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-ui)] border border-border bg-panel p-5 shadow-lg">
          <D.Title className="text-base font-semibold">{title}</D.Title>
          {description && <D.Description className="mt-1 text-sm text-muted">{description}</D.Description>}
          {children}
          <div className="mt-5 flex justify-end gap-2">
            <D.Close className="h-9 rounded-[var(--radius-ui)] border border-border px-4 text-sm">{cancelLabel}</D.Close>
            <button type="button" onClick={onConfirm} disabled={confirmDisabled} className="h-9 rounded-[var(--radius-ui)] bg-sev-high px-4 text-sm font-medium text-white disabled:opacity-50">
              {confirmLabel}
            </button>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
