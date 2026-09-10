import { useController, useFieldArray, type Control } from "react-hook-form";
import { Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { useT, type Key } from "@/lib/i18n";
import { kindForField, leafOf, type PolicyFormValues } from "./policyForm";

type Props = { control: Control<PolicyFormValues>; fields: string[]; ops: string[] };

function fieldLabel(t: (k: Key) => string, field: string): string {
  const key = `policy.field.${leafOf(field)}`;
  const out = t(key as Key);
  return out === key ? field : out;
}

function Row({ control, fields, ops, index, onRemove }: Props & { index: number; onRemove: () => void }) {
  const t = useT();
  const field = useController({ control, name: `when.${index}.field` });
  const op = useController({ control, name: `when.${index}.op` });
  const value = useController({ control, name: `when.${index}.value` });
  const kind = useController({ control, name: `when.${index}.kind` });
  // Una condición cargada puede apuntar a un campo que el catálogo no lista
  // (una señal, p. ej. signal:route_state.route_deviation_m): se añade a las
  // opciones para no perderla al guardar, pero no se puede elegir otra igual.
  const options = fields.includes(field.field.value) ? fields : [field.field.value, ...fields];
  const setField = (next: string) => {
    field.field.onChange(next);
    kind.field.onChange(kindForField(next, op.field.value));
    value.field.onChange("");
  };
  const setOp = (next: string) => {
    op.field.onChange(next);
    kind.field.onChange(kindForField(field.field.value, next));
  };
  const error = value.fieldState.error?.message ?? field.fieldState.error?.message;
  return (
    <div className="grid items-end gap-3 rounded-[var(--radius-ui)] border border-border p-3 sm:grid-cols-[2fr_1fr_2fr_auto]">
      <div className="space-y-1.5">
        <Label htmlFor={`field-${index}`}>{t("policy.when.field")}</Label>
        <NativeSelect id={`field-${index}`} value={field.field.value} onChange={(e) => setField(e.target.value)} aria-invalid={!!field.fieldState.error}>
          {options.map((f) => (
            <option key={f} value={f}>
              {fieldLabel(t, f)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`op-${index}`}>{t("policy.when.op")}</Label>
        <NativeSelect id={`op-${index}`} value={op.field.value} onChange={(e) => setOp(e.target.value)}>
          {ops.map((o) => (
            <option key={o} value={o}>
              {t(`policy.op.${o}` as Key)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`value-${index}`}>{t("policy.when.value")}</Label>
        {kind.field.value === "boolean" ? (
          <NativeSelect id={`value-${index}`} value={value.field.value} onChange={(e) => value.field.onChange(e.target.value)}>
            <option value="true">{t("common.yes")}</option>
            <option value="false">{t("common.no")}</option>
          </NativeSelect>
        ) : (
          <Input
            id={`value-${index}`}
            // Texto, no type="number": un input numérico se traga las letras y
            // el operador vería "está vacío" en vez de "no es un número".
            inputMode={kind.field.value === "number" ? "decimal" : "text"}
            placeholder={kind.field.value === "list" ? t("policy.when.list.help") : undefined}
            aria-invalid={!!value.fieldState.error}
            value={value.field.value}
            onChange={(e) => value.field.onChange(e.target.value)}
          />
        )}
        {error && (
          <p role="alert" className="text-xs text-sev-high">
            {error}
          </p>
        )}
      </div>
      <Button type="button" variant="ghost" size="icon" aria-label={t("policy.when.remove")} onClick={onRemove}>
        <Trash size={16} aria-hidden />
      </Button>
    </div>
  );
}

export function ConditionRows({ control, fields, ops }: Props) {
  const t = useT();
  const rows = useFieldArray({ control, name: "when" });
  const first = fields[0] ?? "";
  const firstOp = ops[0] ?? "eq";
  return (
    <fieldset className="space-y-3">
      <div className="flex items-center justify-between">
        <legend className="text-sm font-medium text-fg-2">{t("policy.when")}</legend>
        <Button type="button" variant="secondary" size="sm" onClick={() => rows.append({ field: first, op: firstOp, value: "", kind: kindForField(first, firstOp) })}>
          {t("policy.when.add")}
        </Button>
      </div>
      <p className="text-sm text-muted">{t("policy.when.help")}</p>
      {rows.fields.map((row, i) => (
        <Row key={row.id} control={control} fields={fields} ops={ops} index={i} onRemove={() => rows.remove(i)} />
      ))}
    </fieldset>
  );
}
