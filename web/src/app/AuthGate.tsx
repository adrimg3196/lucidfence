import { Navigate, Outlet } from "react-router";
import { useAuthStatus, useMe } from "@/api/hooks";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";

export function AuthGate() {
  const status = useAuthStatus();
  const me = useMe();
  if (status.isPending || me.isPending) return <Loading rows={3} />;
  if (status.error) return <ErrorState error={status.error} onRetry={() => status.refetch()} />;
  if (status.data?.setup_required) return <Navigate to="/setup" replace />;
  if (me.error) return <ErrorState error={me.error} onRetry={() => me.refetch()} />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Outlet />;
}
