import type { ReactNode } from "react";
import { Tray } from "@phosphor-icons/react";

export function Empty({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-ui)] border border-dashed border-border px-6 py-14 text-center">
      <Tray size={28} weight="regular" className="text-muted" aria-hidden />
      <p className="mt-3 text-sm font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-[45ch] text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
