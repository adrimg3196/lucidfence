import { useFieldArray, useFormContext, type Control } from "react-hook-form";
import { Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { useT, type Key } from "@/lib/i18n";
import { actionValues, type PolicyFormValues } from "./policyForm";

// Las etiquetas de acción son las de M1 (fence.action.*): son las mismas nueve
// acciones del dominio y traducirlas dos veces sería inventar un segundo sitio
// donde se puede desincronizar el copy.
export function ActionRows({ control }: { control: Control<PolicyFormValues> }) {
  const t = useT();
  const { register } = useFormContext<PolicyFormValues>();
  const rows = useFieldArray({ control, name: "actions" });
  return (
    <fieldset className="space-y-3">
      <div className="flex items-center justify-between">
        <legend className="text-sm font-medium text-fg-2">{t("policy.actions")}</legend>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => rows.append({ action: "notify", text: "", textKey: "text", params: {}, hadParams: false })}
        >
          {t("policy.actions.add")}
        </Button>
      </div>
      {rows.fields.map((row, i) => (
        <div key={row.id} className="grid items-end gap-3 rounded-[var(--radius-ui)] border border-border p-3 sm:grid-cols-[1fr_2fr_auto]">
          <div className="space-y-1.5">
            <Label htmlFor={`action-${i}`}>{t("policy.action")}</Label>
            <NativeSelect id={`action-${i}`} {...register(`actions.${i}.action`)}>
              {actionValues.map((a) => (
                <option key={a} value={a}>
                  {t(`fence.action.${a}` as Key)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`text-${i}`}>{t("policy.action.text")}</Label>
            <Input id={`text-${i}`} {...register(`actions.${i}.text`)} />
          </div>
          <Button type="button" variant="ghost" size="icon" aria-label={t("policy.actions.remove")} onClick={() => rows.remove(i)}>
            <Trash size={16} aria-hidden />
          </Button>
        </div>
      ))}
    </fieldset>
  );
}
