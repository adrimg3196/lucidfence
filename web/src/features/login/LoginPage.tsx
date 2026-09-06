import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { Field } from "@/features/setup/SetupPage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/states/ErrorState";
import { ApiError } from "@/api/client";
import { useLogin } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const schema = z.object({ email: z.email(), password: z.string().min(1) });
type Form = z.infer<typeof schema>;

export function LoginPage() {
  const t = useT();
  const navigate = useNavigate();
  const login = useLogin();
  const [submitError, setSubmitError] = useState<unknown>(null);
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const onSubmit = form.handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      await login.mutateAsync(values);
      navigate("/", { replace: true });
    } catch (e) {
      // login.mutateAsync ya deja el error en login.error, pero lo capturamos
      // también aquí para que se muestre de inmediato sin depender de un
      // re-render adicional de la mutación.
      setSubmitError(e);
    }
  });
  const err = submitError ?? login.error;
  // M1-R27 (C12): antes cualquier ApiError distinto de "throttled" se
  // colapsaba en el mensaje de credenciales inválidas (incluido un 500 del
  // backend), ocultando el fallo real. Solo 401/invalid_credentials y
  // 429/throttled tienen un mensaje propio; el resto se muestra tal cual con
  // ErrorState, que ya sabe presentar el mensaje y código de una ApiError.
  const isInvalidCredentials = err instanceof ApiError && (err.status === 401 || err.code === "invalid_credentials");
  const isThrottled = err instanceof ApiError && (err.status === 429 || err.code === "throttled");
  const message = isInvalidCredentials ? t("login.invalid") : isThrottled ? t("login.throttled") : null;
  const showGenericError = !!err && !isInvalidCredentials && !isThrottled;
  return (
    <AuthLayout title={t("login.title")}>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <Field label={t("login.email")} id="email" error={form.formState.errors.email && "email"}>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label={t("login.password")} id="password" error={form.formState.errors.password && "password"}>
          <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
        </Field>
        {message && (
          <p role="alert" className="rounded-[var(--radius-ui)] border border-sev-high/30 bg-sev-high/5 p-3 text-sm text-fg">
            {message}
          </p>
        )}
        {showGenericError && <ErrorState error={err} />}
        <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
          {t("login.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}
