import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import type { z } from "zod";
import { api, unwrap } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ErrorState } from "@/components/states/ErrorState";
import { keys, useInvalidate, type Settings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { fromNtfy, makeNtfySchema, toNtfy, type NtfyFormValues, type NtfyUpdate } from "./settingsForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

// Mismo patrón que useUpdateRisk (M2-C3): la puerta de hooks de hooks.m2.ts
// queda fuera del alcance de esta ronda, y api/unwrap y keys/useInvalidate ya
// son superficie pública.
function useUpdateNtfy() {
  const invalidate = useInvalidate(keys.settings, keys.engine);
  return useMutation({
    mutationFn: async (body: NtfyUpdate) => unwrap(await api.PUT("/api/v1/settings/ntfy", { body })),
    onSuccess: invalidate,
  });
}

export function NtfyForm({ settings }: { settings: Settings }) {
  const t = useT();
  const update = useUpdateNtfy();
  const schema = useMemo(() => makeNtfySchema(t), [t]);
  const form = useForm<z.input<typeof schema>, unknown, NtfyFormValues>({
    resolver: zodResolver(schema),
    defaultValues: fromNtfy(settings.ntfy),
  });
  const enabled = form.watch("enabled");
  const token = form.watch("token");
  const tokenTouched = form.watch("tokenTouched");
  const errs = form.formState.errors;

  const submit = form.handleSubmit(async (values) => {
    await update.mutateAsync(toNtfy(values));
  });

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <label className="flex items-center gap-3">
        <Switch checked={enabled} onCheckedChange={(c) => form.setValue("enabled", c, { shouldDirty: true })} />
        <span className="text-sm font-medium">{t("settings.ntfy.enabled")}</span>
      </label>

      <div className="space-y-1.5">
        <Label htmlFor="ntfy-url">{t("settings.ntfy.url")}</Label>
        <Input id="ntfy-url" aria-invalid={!!errs.url} {...form.register("url")} />
        <FieldError message={errs.url?.message} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ntfy-token">{t("settings.ntfy.token")}</Label>
        {settings.ntfy.token_set && !tokenTouched && <p className="text-sm text-muted">{t("settings.ntfy.token.set")}</p>}
        <div className="flex gap-2">
          <Input
            id="ntfy-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => {
              form.setValue("token", e.target.value, { shouldDirty: true });
              form.setValue("tokenTouched", true, { shouldDirty: true });
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              form.setValue("token", "", { shouldDirty: true });
              form.setValue("tokenTouched", true, { shouldDirty: true });
            }}
          >
            {t("fences.delete")}
          </Button>
        </div>
        <p className="text-xs text-muted">{t("settings.ntfy.token.help")}</p>
      </div>

      {update.error && <ErrorState error={update.error} />}
      <Button type="submit" disabled={update.isPending}>
        {t("fence.save")}
      </Button>
    </form>
  );
}
