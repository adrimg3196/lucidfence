import { Dialog as D } from "radix-ui";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { SeverityBadge } from "@/components/SeverityBadge";
import { usePolicyTemplates, type Policy } from "@/api/hooks";
import { useT } from "@/lib/i18n";

export function TemplatesDialog({ open, onOpenChange, onPick }: { open: boolean; onOpenChange: (o: boolean) => void; onPick: (p: Policy) => void }) {
  const t = useT();
  const templates = usePolicyTemplates();
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-fg/40" />
        <D.Content className="fixed left-1/2 top-1/2 max-h-[80vh] w-[min(92vw,640px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[var(--radius-ui)] border border-border bg-panel p-5 shadow-lg">
          <D.Title className="text-base font-semibold">{t("policy.templates.title")}</D.Title>
          <D.Description className="mt-1 text-sm text-muted">{t("policy.templates.help")}</D.Description>
          <div className="mt-4 space-y-3">
            {templates.isPending && <Loading rows={3} />}
            {templates.error && <ErrorState error={templates.error} onRetry={() => templates.refetch()} />}
            {templates.data?.items.map((p) => (
              <div key={p.id} className="flex items-start justify-between gap-4 rounded-[var(--radius-ui)] border border-border p-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{p.name}</p>
                    <SeverityBadge severity={p.severity} />
                  </div>
                  <p className="text-sm text-muted">{p.description}</p>
                </div>
                <Button type="button" size="sm" onClick={() => onPick(p)}>
                  {t("policy.templates.use")}
                </Button>
              </div>
            ))}
          </div>
          <div className="mt-5 flex justify-end">
            <D.Close className="h-9 rounded-[var(--radius-ui)] border border-border px-4 text-sm">{t("policy.cancel")}</D.Close>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
