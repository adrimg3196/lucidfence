import type { ReactNode } from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "@/lib/query";
import { api } from "@/api/client";
import {
  keys,
  usePolicies,
  useCreatePolicy,
  useReplayPolicy,
  useIncidents,
  usePatchIncident,
  useAlerts,
  useCreateAlert,
  usePlaybooks,
  useHandoffs,
  useApproveHandoff,
  useSettings,
  useUpdateEnforcement,
  useValidateSettings,
  useDeviceAction,
  useEventsPage,
  useActionsPage,
} from "@/api/hooks";

vi.mock("@/api/client", async (orig) => {
  const actual = await orig<typeof import("@/api/client")>();
  return { ...actual, api: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() } };
});

const ok = (data: unknown) => ({ data, response: { ok: true, status: 200 } }) as never;

function conCliente() {
  const qc = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  return { qc, wrapper };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.GET).mockResolvedValue(ok({ items: [], total: 0 }));
  vi.mocked(api.POST).mockResolvedValue(ok({ id: "x" }));
  vi.mocked(api.PUT).mockResolvedValue(ok({ id: "x" }));
  vi.mocked(api.PATCH).mockResolvedValue(ok({ id: "x" }));
  vi.mocked(api.DELETE).mockResolvedValue(ok(undefined));
});

test("las consultas de políticas, incidentes, alertas y playbooks piden su ruta", async () => {
  const { wrapper } = conCliente();
  const { result } = renderHook(
    () => ({ p: usePolicies(), i: useIncidents({ status: "open", device_id: "dev-001" }), a: useAlerts(), b: usePlaybooks(), s: useSettings() }),
    { wrapper },
  );
  await waitFor(() => expect(result.current.p.isSuccess).toBe(true));
  expect(api.GET).toHaveBeenCalledWith("/api/v1/policies");
  expect(api.GET).toHaveBeenCalledWith("/api/v1/incidents", { params: { query: { status: "open", device_id: "dev-001" } } });
  expect(api.GET).toHaveBeenCalledWith("/api/v1/alerts");
  expect(api.GET).toHaveBeenCalledWith("/api/v1/playbooks");
  expect(api.GET).toHaveBeenCalledWith("/api/v1/settings");
});

test("la bandeja filtra por estado y las páginas viajan con cursor y límite fijo", async () => {
  const { wrapper } = conCliente();
  const { result } = renderHook(() => ({ h: useHandoffs("pending"), e: useEventsPage("c2"), a: useActionsPage() }), { wrapper });
  await waitFor(() => expect(result.current.h.isSuccess).toBe(true));
  expect(api.GET).toHaveBeenCalledWith("/api/v1/handoffs", { params: { query: { status: "pending" } } });
  expect(api.GET).toHaveBeenCalledWith("/api/v1/events", { params: { query: { limit: 50, cursor: "c2" } } });
  expect(api.GET).toHaveBeenCalledWith("/api/v1/actions", { params: { query: { limit: 50 } } });
  expect(keys.eventsPage("c2")).toEqual(["events", "page", "c2"]);
  expect(keys.actionsPage()).toEqual(["actions", "page", ""]);
});

test("crear una política y una regla invalida su colección", async () => {
  const { qc, wrapper } = conCliente();
  const espia = vi.spyOn(qc, "invalidateQueries");
  const { result } = renderHook(() => ({ p: useCreatePolicy(), a: useCreateAlert() }), { wrapper });
  await act(async () => {
    await result.current.p.mutateAsync({ id: "pol-1", name: "Salida sin cifrado" } as never);
    await result.current.a.mutateAsync({ id: "al-1", name: "Batería baja" } as never);
  });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/policies", { body: { id: "pol-1", name: "Salida sin cifrado" } });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/alerts", { body: { id: "al-1", name: "Batería baja" } });
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.policies });
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.alerts });
});

test("el patch de un incidente manda el cuerpo y refresca lista, detalle y analítica", async () => {
  const { qc, wrapper } = conCliente();
  const espia = vi.spyOn(qc, "invalidateQueries");
  const { result } = renderHook(() => usePatchIncident(), { wrapper });
  await act(async () => {
    await result.current.mutateAsync({ id: "inc-1", patch: { status: "ack", assignee: "adri@x.com", note: "lo miro yo" } });
  });
  expect(api.PATCH).toHaveBeenCalledWith("/api/v1/incidents/{id}", {
    params: { path: { id: "inc-1" } },
    body: { status: "ack", assignee: "adri@x.com", note: "lo miro yo" },
  });
  expect(espia).toHaveBeenCalledWith({ queryKey: ["incidents"] });
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.incidentAnalytics });
});

test("aprobar un handoff firma la ruta con su id y refresca bandeja, acciones y motor", async () => {
  const { qc, wrapper } = conCliente();
  const espia = vi.spyOn(qc, "invalidateQueries");
  const { result } = renderHook(() => useApproveHandoff(), { wrapper });
  await act(async () => {
    await result.current.mutateAsync({ id: "ho-dev-001-pb-1-lock", note: "autorizado por soporte" });
  });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/handoffs/{id}/approve", {
    params: { path: { id: "ho-dev-001-pb-1-lock" } },
    body: { note: "autorizado por soporte" },
  });
  expect(espia).toHaveBeenCalledWith({ queryKey: ["handoffs"] });
  expect(espia).toHaveBeenCalledWith({ queryKey: ["actions"] });
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.engine });
});

test("la acción manual manda acción y parámetros y el what-if no invalida nada", async () => {
  const { qc, wrapper } = conCliente();
  const espia = vi.spyOn(qc, "invalidateQueries");
  const { result } = renderHook(() => ({ d: useDeviceAction(), r: useReplayPolicy() }), { wrapper });
  await act(async () => {
    await result.current.d.mutateAsync({ id: "dev-001", action: "lock", params: { message: "equipo perdido" } });
  });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/devices/{id}/actions", {
    params: { path: { id: "dev-001" } },
    body: { action: "lock", params: { message: "equipo perdido" } },
  });
  expect(espia).toHaveBeenCalledWith({ queryKey: ["actions"] });
  espia.mockClear();
  await act(async () => {
    await result.current.r.mutateAsync({ policy: { id: "pol-1" }, limit: 5000, use_current_fences: true } as never);
  });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/policies/replay", { body: { policy: { id: "pol-1" }, limit: 5000, use_current_fences: true } });
  expect(espia).not.toHaveBeenCalled();
});

test("los ajustes se guardan por bloques y la comprobación va sin cuerpo", async () => {
  const { qc, wrapper } = conCliente();
  const espia = vi.spyOn(qc, "invalidateQueries");
  const { result } = renderHook(() => ({ e: useUpdateEnforcement(), v: useValidateSettings() }), { wrapper });
  await act(async () => {
    await result.current.e.mutateAsync({ mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 } as never);
    await result.current.v.mutateAsync();
  });
  expect(api.PUT).toHaveBeenCalledWith("/api/v1/settings/enforcement", {
    body: { mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 },
  });
  expect(api.POST).toHaveBeenCalledWith("/api/v1/settings/validate");
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.settings });
  expect(espia).toHaveBeenCalledWith({ queryKey: keys.engine });
});
