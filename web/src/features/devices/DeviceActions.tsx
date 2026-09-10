import { useState } from "react";
import { Dialog as D } from "radix-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/states/ErrorState";
import { useDeviceAction, useMe, type ActionResult, type Device, type DeviceActionRequest } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";
import { ApiError } from "@/api/client";

type ActionKind = DeviceActionRequest["action"];

// Destructivas = action.Action.Destructive() en el dominio (T1): lock, wipe,
// clear_passcode, reboot. Todas pasan por el mismo diálogo reforzado.
const DESTRUCTIVE: ActionKind[] = ["lock", "wipe", "reboot", "clear_passcode"];
const TEXT_ACTIONS: ActionKind[] = ["message", "notify"];

export function DeviceActions({ device }: { device: Device }) {
  const t = useT();
  const me = useMe();
  const deviceAction = useDeviceAction();
  const [confirming, setConfirming] = useState<ActionKind | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  if (!can(me.data?.capabilities, "device:action")) return null;

  const run = (action: ActionKind, params?: Record<string, unknown>) => {
    deviceAction.mutate({ id: device.id, action, ...(params ? { params } : {}) });
  };
  const setDraft = (key: string, v: string) => setDrafts((d) => ({ ...d, [key]: v }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={() => run("locate")} disabled={deviceAction.isPending}>
          {t("fence.action.locate")}
        </Button>
        {DESTRUCTIVE.map((a) => (
          <Button key={a} variant="destructive" size="sm" onClick={() => setConfirming(a)} disabled={deviceAction.isPending}>
            {t(`fence.action.${a}`)}
          </Button>
        ))}
        <Button variant="secondary" size="sm" onClick={() => run("set_compliance", { compliant: true })} disabled={deviceAction.isPending}>
          {t("device.action.compliance.yes")}
        </Button>
        <Button variant="secondary" size="sm" onClick={() => run("set_compliance", { compliant: false })} disabled={deviceAction.isPending}>
          {t("device.action.compliance.no")}
        </Button>
      </div>
      {TEXT_ACTIONS.map((a) => (
        <div key={a} className="flex items-end gap-2">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor={`draft-${a}`}>{`${t(`fence.action.${a}`)} · ${t("fence.action.text")}`}</Label>
            <Input id={`draft-${a}`} value={drafts[a] ?? ""} onChange={(e) => setDraft(a, e.target.value)} />
          </div>
          <Button size="sm" disabled={!drafts[a]?.trim() || deviceAction.isPending} onClick={() => run(a, { text: drafts[a] })}>
            {t("device.action.send")}
          </Button>
        </div>
      ))}
      <div className="flex items-end gap-2">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="draft-custom">{`${t("fence.action.custom")} · ${t("device.action.custom.type")}`}</Label>
          <Input id="draft-custom" value={drafts.custom ?? ""} onChange={(e) => setDraft("custom", e.target.value)} />
        </div>
        <Button size="sm" disabled={!drafts.custom?.trim() || deviceAction.isPending} onClick={() => run("custom", { type: drafts.custom })}>
          {t("device.action.send")}
        </Button>
      </div>
      {deviceAction.error && <ActionFeedback error={deviceAction.error} />}
      {deviceAction.data && <ActionResultBanner result={deviceAction.data} />}
      {confirming && (
        <DestructiveConfirm
          device={device}
          action={confirming}
          pending={deviceAction.isPending}
          onCancel={() => setConfirming(null)}
          onConfirm={() => {
            run(confirming);
            setConfirming(null);
          }}
        />
      )}
    </div>
  );
}

// Una supresión por cooldown (T20: 409 "cooldown", detail.retry_after en RFC
// 3339) es la única forma en la que una acción manual no deja ActionResult
// que enseñar: no hay más que decir salvo cuándo volverá a estar disponible.
function ActionFeedback({ error }: { error: unknown }) {
  const t = useT();
  const { lang } = useLang();
  if (error instanceof ApiError && error.code === "cooldown") {
    const retryAfter = (error.detail as { retry_after?: string } | undefined)?.retry_after;
    return (
      <div role="alert" className="rounded-[var(--radius-ui)] border border-sev-medium/30 bg-sev-medium/5 p-3 text-sm text-fg">
        {t("device.action.cooldown", { when: retryAfter ? formatDateTime(retryAfter, lang) : t("common.unknown") })}
      </div>
    );
  }
  return <ErrorState error={error} />;
}

// El ActionResult se enseña tal cual: bloqueada gana a dry-run, dry-run gana a
// ejecutada, y un ok:false que no es ni bloqueo ni simulación es un fallo real
// del conector (T20: blocked/dry_run son las dos formas honestas de "no se
// tocó el dispositivo"; lo demás es un intento real que no funcionó).
function ActionResultBanner({ result }: { result: ActionResult }) {
  const t = useT();
  const kind = result.action as ActionKind;
  // set_compliance es la única acción cuyo "qué se hizo" no cabe en su nombre:
  // la dirección viaja en los params y el resultado los devuelve tal cual
  // (action.Result.Params, lo mismo desde el conector que desde el
  // guardarraíl). Sin leerlos, la mitad de las veces el banner diría lo
  // contrario de lo que el operador acaba de ejecutar.
  const compliant = result.params?.compliant;
  const label =
    kind === "set_compliance" && typeof compliant === "boolean"
      ? t(compliant ? "device.action.compliance.yes" : "device.action.compliance.no")
      : t(`fence.action.${kind}`);
  let status = t("device.action.result.executed");
  let variant: "success" | "info" | "danger" = "success";
  if (!result.ok && !result.blocked && !result.dry_run) {
    status = result.error || t("state.error");
    variant = "danger";
  }
  if (result.dry_run) {
    status = t("device.action.result.dryRun");
    variant = "info";
  }
  if (result.blocked) {
    status = t("device.action.result.blocked");
    variant = "danger";
  }
  return (
    <div role="status" className="flex items-center gap-2 rounded-[var(--radius-ui)] border border-border bg-bg-2 p-3 text-sm">
      <Badge variant={variant}>{status}</Badge>
      <span className="text-muted">{label}</span>
      {result.note && <span className="text-muted">· {result.note}</span>}
    </div>
  );
}

// La fricción deliberada de las cuatro acciones destructivas: hay que teclear
// el identificador exacto del dispositivo, no basta un solo clic.
function DestructiveConfirm({
  device,
  action,
  onCancel,
  onConfirm,
  pending,
}: {
  device: Device;
  action: ActionKind;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  const t = useT();
  const [typed, setTyped] = useState("");
  const ready = typed.trim() === device.id;
  return (
    <D.Root open onOpenChange={(o) => !o && onCancel()}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-fg/40" />
        <D.Content className="fixed left-1/2 top-1/2 w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-ui)] border border-border bg-panel p-5 shadow-lg">
          <D.Title className="text-base font-semibold">{t("device.action.confirm.title", { action: t(`fence.action.${action}`) })}</D.Title>
          <D.Description className="mt-1 text-sm text-muted">{t("device.action.confirm.warning")}</D.Description>
          <div className="mt-3 space-y-1.5">
            <Label htmlFor="confirm-id">{t("device.action.confirm.confirmId", { id: device.id })}</Label>
            <Input id="confirm-id" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={device.id} />
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <D.Close className="h-9 rounded-[var(--radius-ui)] border border-border px-4 text-sm">{t("device.action.cancel")}</D.Close>
            <button type="button" disabled={!ready || pending} onClick={onConfirm} className="h-9 rounded-[var(--radius-ui)] bg-sev-high px-4 text-sm font-medium text-white disabled:opacity-50">
              {t("device.action.confirm.submit")}
            </button>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
