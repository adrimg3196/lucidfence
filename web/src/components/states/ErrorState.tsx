import { WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { ApiError } from "@/api/client";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  const message = error instanceof ApiError ? `${error.message} (${error.code})` : error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start gap-3 rounded-[var(--radius-ui)] border border-sev-high/30 bg-sev-high/5 p-4">
      <WarningCircle size={20} className="mt-0.5 shrink-0 text-sev-high" aria-hidden />
      <div className="flex-1">
        <p className="text-sm font-medium text-fg">{t("state.error")}</p>
        <p className="mt-0.5 break-words text-sm text-fg-2">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {t("state.retry")}
        </Button>
      )}
    </div>
  );
}
