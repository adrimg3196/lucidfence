import { useMemo } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorState } from "@/components/states/ErrorState";
import { useUpdateEnforcement, type Settings } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { actionOptions, fromEnforcement, makeEnforcementSchema, toEnforcement, type EnforcementFormValues } from "./settingsForm";

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-xs text-sev-high">
      {message}
    </p>
  );
}

export function EnforcementForm({ settings }: { settings: Settings }) {
  const t = useT();
  const update = useUpdateEnforcement();
  const schema = useMemo(() => makeEnforcementSchema(t), [t]);
  const form = useForm<z.input<typeof schema>, unknown, EnforcementFormValues>({
    resolver: zodResolver(schema),
    defaultValues: fromEnforcement(settings.enforcement),
  });
  const wipeAllowlist = useFieldArray({ control: form.control, name: "wipeAllowlist" });
  const mode = form.watch("mode");
  const liveActions = form.watch("liveActions");
  const errs = form.formState.errors;
  const enforcing = mode === "enforce";

  const submit = form.handleSubmit(async (values) => {
    await update.mutateAsync(toEnforcement(values));
  });

  const toggleAction = (a: (typeof actionOptions)[number], checked: boolean) => {
    const next = checked ? [...liveActions, a] : liveActions.filter((x) => x !== a);
    form.setValue(
      "liveActions",
      actionOptions.filter((o) => next.includes(o)),
      { shouldDirty: true },
    );
  };

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <div className="space-y-1.5">
        <Label>{t("settings.enforcement.mode")}</Label>
        <label className="flex items-center gap-3">
          <Switch checked={enforcing} onCheckedChange={(c) => form.setValue("mode", c ? "enforce" : "observe", { shouldDirty: true })} />
          <span className="text-sm font-medium">{t(enforcing ? "settings.enforcement.mode.enforce" : "settings.enforcement.mode.observe")}</span>
        </label>
        <p className="text-sm text-muted">{t("settings.enforcement.mode.help")}</p>
        {enforcing && (
          <p className="rounded-[var(--radius-ui)] border border-sev-medium/30 bg-sev-medium/5 p-3 text-sm text-sev-medium">
            {t("settings.enforcement.mode.enforce.warning")}
          </p>
        )}
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-fg-2">{t("settings.enforcement.liveActions")}</legend>
        <p className="text-xs text-muted">{t("settings.enforcement.liveActions.help")}</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
          {actionOptions.map((a) => (
            <label key={a} className="flex items-center gap-2 text-sm">
              <Checkbox checked={liveActions.includes(a)} onCheckedChange={(c) => toggleAction(a, c === true)} />
              {t(`fence.action.${a}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor="actionCooldownSeconds">{t("settings.enforcement.cooldown")}</Label>
        <Input
          id="actionCooldownSeconds"
          type="number"
          step="1"
          min="0"
          aria-invalid={!!errs.actionCooldownSeconds}
          {...form.register("actionCooldownSeconds")}
        />
        <p className="text-xs text-muted">{t("settings.enforcement.cooldown.help")}</p>
        <FieldError message={errs.actionCooldownSeconds?.message} />
      </div>

      <fieldset disabled={!enforcing} className="space-y-3 rounded-[var(--radius-ui)] border border-border p-4">
        <legend className="px-1 text-sm font-medium text-fg-2">{t("settings.enforcement.allowWipe")}</legend>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            disabled={!enforcing}
            checked={form.watch("allowWipe")}
            onCheckedChange={(c) => form.setValue("allowWipe", c === true, { shouldDirty: true })}
          />
          {t("settings.enforcement.allowWipe")}
        </label>
        <p className="text-sm text-muted">{t("settings.enforcement.allowWipe.help")}</p>
        <div className="space-y-2">
          <Label>{t("settings.enforcement.wipeAllowlist")}</Label>
          <p className="text-xs text-muted">{t("settings.enforcement.wipeAllowlist.help")}</p>
          {wipeAllowlist.fields.map((f, i) => (
            <div key={f.id} className="flex items-center gap-2">
              <Input disabled={!enforcing} aria-invalid={!!errs.wipeAllowlist?.[i]?.value} {...form.register(`wipeAllowlist.${i}.value`)} />
              <FieldError message={errs.wipeAllowlist?.[i]?.value?.message} />
              <Button type="button" variant="ghost" size="icon" disabled={!enforcing} aria-label={t("fences.delete")} onClick={() => wipeAllowlist.remove(i)}>
                <Trash size={16} aria-hidden />
              </Button>
            </div>
          ))}
          <Button type="button" variant="secondary" size="sm" disabled={!enforcing} onClick={() => wipeAllowlist.append({ value: "" })}>
            {t("settings.add")}
          </Button>
        </div>
      </fieldset>

      {update.error && <ErrorState error={update.error} />}
      <Button type="submit" disabled={update.isPending}>
        {t("fence.save")}
      </Button>
    </form>
  );
}
