import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { ErrorState } from "@/components/states/ErrorState";
import { useUpdateWebhooks, type Settings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { fromWebhook, makeWebhookSchema, toWebhook, webhookEventOptions, type WebhookFormValues } from "./settingsForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function WebhooksForm({ settings }: { settings: Settings }) {
  const t = useT();
  const update = useUpdateWebhooks();
  const schema = useMemo(() => makeWebhookSchema(t), [t]);
  // Mismo patrón de tres genéricos que EnforcementForm.tsx (y
  // FenceEditorPage/AlertsPage, M1): el resolver infiere `events` como la
  // unión estricta del enum a partir del esquema (z.input), no como el
  // `string[]` más laxo de WebhookFormValues; con un solo genérico el
  // Resolver de react-hook-form no es asignable por varianza de parámetros.
  const form = useForm<z.input<typeof schema>, unknown, WebhookFormValues>({
    resolver: zodResolver(schema),
    // `events` es `string[]` en WebhookFormValues (así lo fija el "Produces"
    // del brief) pero z.input<schema>.events es la unión estricta del enum;
    // el propio formulario solo puede producir valores de webhookEventOptions
    // (los checkboxes de abajo son el único origen), así que el cast es
    // seguro en tiempo de ejecución.
    defaultValues: fromWebhook(settings.webhook) as z.input<typeof schema>,
  });
  const format = form.watch("format");
  const enabled = form.watch("enabled");
  const events = form.watch("events");
  const secret = form.watch("secret");
  const secretTouched = form.watch("secretTouched");
  const errs = form.formState.errors;

  const submit = form.handleSubmit(async (values) => {
    await update.mutateAsync(toWebhook(values));
  });

  const toggleEvent = (ev: string, checked: boolean) => {
    const next = checked ? [...events, ev] : events.filter((e) => e !== ev);
    form.setValue(
      "events",
      webhookEventOptions.filter((o) => next.includes(o)),
      { shouldDirty: true },
    );
  };

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <label className="flex items-center gap-3">
        <Switch checked={enabled} onCheckedChange={(c) => form.setValue("enabled", c, { shouldDirty: true })} />
        <span className="text-sm font-medium">{t("settings.webhook.enabled")}</span>
      </label>

      <div className="space-y-1.5">
        <Label htmlFor="url">{t("settings.webhook.url")}</Label>
        <Input id="url" aria-invalid={!!errs.url} {...form.register("url")} />
        <FieldError message={errs.url?.message} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="format">{t("settings.webhook.format")}</Label>
        <NativeSelect id="format" {...form.register("format")}>
          <option value="native">{t("settings.webhook.format.native")}</option>
          <option value="ocsf">{t("settings.webhook.format.ocsf")}</option>
        </NativeSelect>
        {format === "ocsf" && <p className="text-sm text-sev-medium">{t("settings.webhook.format.ocsf.help")}</p>}
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg-2">{t("settings.webhook.events")}</legend>
        {webhookEventOptions.map((ev) => (
          <label key={ev} className="flex items-center gap-2 text-sm">
            <Checkbox checked={events.includes(ev)} onCheckedChange={(c) => toggleEvent(ev, c === true)} />
            <span className="font-mono text-xs">{ev}</span>
          </label>
        ))}
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor="secret">{t("settings.webhook.secret")}</Label>
        {settings.webhook.secret_set && !secretTouched && <p className="text-sm text-muted">{t("settings.webhook.secret.set")}</p>}
        <div className="flex gap-2">
          <Input
            id="secret"
            type="password"
            autoComplete="off"
            value={secret}
            onChange={(e) => {
              form.setValue("secret", e.target.value, { shouldDirty: true });
              form.setValue("secretTouched", true, { shouldDirty: true });
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              form.setValue("secret", "", { shouldDirty: true });
              form.setValue("secretTouched", true, { shouldDirty: true });
            }}
          >
            {t("fences.delete")}
          </Button>
        </div>
        <p className="text-xs text-muted">{t("settings.webhook.secret.help")}</p>
      </div>

      {update.error && <ErrorState error={update.error} />}
      <Button type="submit" disabled={update.isPending}>
        {t("fence.save")}
      </Button>
    </form>
  );
}
