import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, setCsrf, unwrap } from "./client";
import { keys, useInvalidate } from "./keys";
import type { components } from "./schema";

export { keys, useInvalidate };
export * from "./hooks.m2";

export type Device = components["schemas"]["Device"];
export type Fence = components["schemas"]["Fence"];
export type Route = components["schemas"]["Route"];
export type POI = components["schemas"]["POI"];
export type Transition = components["schemas"]["Transition"];
export type ActionResult = components["schemas"]["ActionResult"];
export type EngineStatus = components["schemas"]["EngineStatus"];
export type CycleStats = components["schemas"]["CycleStats"];
export type Health = components["schemas"]["Health"];
export type SessionResponse = components["schemas"]["SessionResponse"];
export type TrailPoint = components["schemas"]["TrailPoint"];

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: async () => unwrap(await api.GET("/api/v1/health")) });
}

export function useAuthStatus() {
  return useQuery({ queryKey: keys.authStatus, queryFn: async () => unwrap(await api.GET("/api/v1/auth/status")) });
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        const me = unwrap(await api.GET("/api/v1/auth/me"));
        setCsrf(me.csrf);
        return me;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });
}

function useSessionMutation<TBody>(path: "/api/v1/auth/setup" | "/api/v1/auth/login") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TBody) => {
      const res = await api.POST(path, { body: body as never });
      const session = unwrap(res) as SessionResponse;
      setCsrf(session.csrf);
      return session;
    },
    onSuccess: (session) => {
      qc.setQueryData(keys.me, session);
      qc.setQueryData(keys.authStatus, { setup_required: false });
    },
  });
}

export function useSetup() {
  return useSessionMutation<components["schemas"]["SetupRequest"]>("/api/v1/auth/setup");
}

export function useLogin() {
  return useSessionMutation<components["schemas"]["LoginRequest"]>("/api/v1/auth/login");
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/v1/auth/logout"));
      setCsrf("");
    },
    onSuccess: () => {
      qc.setQueryData(keys.me, null);
      qc.clear();
    },
  });
}

export function useDevices(params?: { state?: string; q?: string; severity?: string }) {
  return useQuery({
    queryKey: keys.devices(params),
    queryFn: async () => unwrap(await api.GET("/api/v1/devices", { params: { query: params as never } })),
    refetchInterval: 15_000,
  });
}

export function useDevice(id: string) {
  return useQuery({ queryKey: keys.device(id), queryFn: async () => unwrap(await api.GET("/api/v1/devices/{id}", { params: { path: { id } } })), enabled: !!id });
}

export function useDeviceTrail(id: string, limit = 200) {
  return useQuery({
    queryKey: keys.trail(id, limit),
    queryFn: async () => unwrap(await api.GET("/api/v1/devices/{id}/trail", { params: { path: { id }, query: { limit } } })),
    enabled: !!id,
  });
}

export function useFences() {
  return useQuery({ queryKey: keys.fences, queryFn: async () => unwrap(await api.GET("/api/v1/fences")) });
}

export function useFence(id: string) {
  return useQuery({ queryKey: keys.fence(id), queryFn: async () => unwrap(await api.GET("/api/v1/fences/{id}", { params: { path: { id } } })), enabled: !!id });
}

export function useCreateFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({ mutationFn: async (body: Fence) => unwrap(await api.POST("/api/v1/fences", { body })), onSuccess: invalidate });
}

export function useUpdateFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({
    mutationFn: async (body: Fence) => unwrap(await api.PUT("/api/v1/fences/{id}", { params: { path: { id: body.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({ mutationFn: async (id: string) => unwrap(await api.DELETE("/api/v1/fences/{id}", { params: { path: { id } } })), onSuccess: invalidate });
}

export function useEngineStatus() {
  return useQuery({ queryKey: keys.engine, queryFn: async () => unwrap(await api.GET("/api/v1/engine/status")), refetchInterval: 15_000 });
}

export function useRunOnce() {
  const invalidate = useInvalidate(keys.engine, ["devices"], ["events"], ["actions"]);
  return useMutation({ mutationFn: async () => unwrap(await api.POST("/api/v1/engine/run-once")), onSuccess: invalidate });
}

export function useEvents(limit = 20) {
  return useQuery({ queryKey: keys.events(limit), queryFn: async () => unwrap(await api.GET("/api/v1/events", { params: { query: { limit } } })), refetchInterval: 15_000 });
}

export function useActions(limit = 20) {
  return useQuery({ queryKey: keys.actions(limit), queryFn: async () => unwrap(await api.GET("/api/v1/actions", { params: { query: { limit } } })) });
}
