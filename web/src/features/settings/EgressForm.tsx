import { useMemo } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Trash } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorState } from "@/components/states/ErrorState";
import { useUpdateEgress, useValidateSettings, type Settings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { fromEgress, makeEgressSchema, toEgress, type EgressFormValues } from "./settingsForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function EgressForm({ settings }: { settings: Settings }) {
  const t = useT();
  const update = useUpdateEgress();
  const validate = useValidateSettings();
  const schema = useMemo(() => makeEgressSchema(t), [t]);
  const form = useForm<EgressFormValues>({ resolver: zodResolver(schema), defaultValues: fromEgress(settings.egress) });
  const hosts = useFieldArray({ control: form.control, name: "hosts" });
  const errs = form.formState.errors;

  const submit = form.handleSubmit(async (values) => {
    await update.mutateAsync(toEgress(values));
  });

  const problems = validate.data ? validate.data.channels.filter((c) => !c.ok).length : 0;

  return (
    <div className="max-w-2xl space-y-8">
      <form onSubmit={submit} noValidate className="space-y-6">
        <div className="space-y-2">
          <Label>{t("settings.egress.hosts")}</Label>
          <p className="text-xs text-muted">{t("settings.egress.hosts.help")}</p>
          {hosts.fields.map((f, i) => (
            <div key={f.id} className="flex items-center gap-2">
              <Input aria-invalid={!!errs.hosts?.[i]?.value} {...form.register(`hosts.${i}.value`)} />
              <FieldError message={errs.hosts?.[i]?.value?.message} />
              <Button type="button" variant="ghost" size="icon" aria-label={t("fences.delete")} onClick={() => hosts.remove(i)}>
                <Trash size={16} aria-hidden />
              </Button>
            </div>
          ))}
          <Button type="button" variant="secondary" size="sm" onClick={() => hosts.append({ value: "" })}>
            {t("settings.add")}
          </Button>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={form.watch("allowPrivate")} onCheckedChange={(c) => form.setValue("allowPrivate", c === true, { shouldDirty: true })} />
          {t("settings.egress.allowPrivate")}
        </label>
        <p className="text-xs text-muted">{t("settings.egress.allowPrivate.help")}</p>

        {update.error && <ErrorState error={update.error} />}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={update.isPending}>
            {t("fence.save")}
          </Button>
          {update.isSuccess && <span className="text-sm text-sev-low">{t("settings.saved")}</span>}
        </div>
      </form>

      <div className="space-y-3 border-t border-border pt-6">
        <p className="text-xs text-muted">{t("settings.validate.help")}</p>
        <div className="flex items-center gap-3">
          <Button type="button" variant="secondary" onClick={() => validate.mutate()} disabled={validate.isPending}>
            {t("settings.validate")}
          </Button>
          {validate.data && (
            <span className={validate.data.ok ? "text-sm text-sev-low" : "text-sm text-sev-high"}>
              {validate.data.ok ? t("settings.validate.ok") : t("settings.validate.problems", { count: problems })}
            </span>
          )}
        </div>
        {validate.error && <ErrorState error={validate.error} />}
        {validate.data?.error && <p className="text-sm text-sev-high">{validate.data.error}</p>}
        {validate.data?.channels.map((c) => (
          <div key={c.channel} className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-2 text-sm last:border-0">
            <span className="font-medium">{c.channel === "webhook" ? "Webhook" : "ntfy"}</span>
            {!c.enabled ? (
              <span className="text-muted">{t("common.no")}</span>
            ) : c.ok ? (
              <Badge variant="success">{t("settings.validate.ok")}</Badge>
            ) : (
              <span className="text-sev-high">{c.reason}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
