import { useMutation, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { keys, useInvalidate } from "./keys";
import type { components } from "./schema";

export type Policy = components["schemas"]["Policy"];
export type PolicyCondition = components["schemas"]["PolicyCondition"];
export type PolicyAction = components["schemas"]["PolicyAction"];
// Una plantilla es una política sellada con template_id y source: mismo tipo.
export type PolicyTemplate = Policy;
export type PolicyFieldCatalog = components["schemas"]["PolicyFieldCatalog"];
export type ReplayRequest = components["schemas"]["ReplayRequest"];
export type ReplayResult = components["schemas"]["ReplayResult"];
export type Incident = components["schemas"]["Incident"];
export type IncidentPatch = components["schemas"]["IncidentPatch"];
export type IncidentAnalytics = components["schemas"]["IncidentAnalytics"];
export type AlertRule = components["schemas"]["AlertRule"];
export type AlertFiring = components["schemas"]["AlertFiring"];
export type AlertEvaluation = components["schemas"]["AlertEvaluation"];
export type Playbook = components["schemas"]["Playbook"];
export type Handoff = components["schemas"]["Handoff"];
export type Settings = components["schemas"]["Settings"];
export type EnforcementSettings = components["schemas"]["EnforcementSettings"];
export type WebhookSettings = components["schemas"]["WebhookSettings"];
export type EgressSettings = components["schemas"]["EgressSettings"];
export type SettingsValidation = components["schemas"]["SettingsValidation"];
export type DeviceActionRequest = components["schemas"]["DeviceActionRequest"];
export type EventPage = components["schemas"]["EventPage"];
export type ActionPage = components["schemas"]["ActionPage"];

// El motor abre y cierra incidentes y handoffs por su cuenta: eso es lo único
// que se sondea. La configuración la escriben personas y se invalida al guardar.
const POLL_MS = 15_000;
// El cursor es la única variable de la clave de una página; el tamaño se fija
// aquí para que dos vistas no compartan caché con límites distintos.
export const PAGE_SIZE = 50;

export function usePolicies() {
  return useQuery({ queryKey: keys.policies, queryFn: async () => unwrap(await api.GET("/api/v1/policies")) });
}

export function usePolicy(id: string) {
  return useQuery({
    queryKey: keys.policy(id),
    queryFn: async () => unwrap(await api.GET("/api/v1/policies/{id}", { params: { path: { id } } })),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const invalidate = useInvalidate(keys.policies);
  return useMutation({ mutationFn: async (body: Policy) => unwrap(await api.POST("/api/v1/policies", { body })), onSuccess: invalidate });
}

export function useUpdatePolicy() {
  const invalidate = useInvalidate(keys.policies);
  return useMutation({
    mutationFn: async (body: Policy) => unwrap(await api.PUT("/api/v1/policies/{id}", { params: { path: { id: body.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeletePolicy() {
  const invalidate = useInvalidate(keys.policies);
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.DELETE("/api/v1/policies/{id}", { params: { path: { id } } })),
    onSuccess: invalidate,
  });
}

export function usePolicyTemplates() {
  return useQuery({ queryKey: keys.policyTemplates, queryFn: async () => unwrap(await api.GET("/api/v1/policies/templates")), staleTime: Infinity });
}

export function usePolicyFields() {
  return useQuery({ queryKey: keys.policyFields, queryFn: async () => unwrap(await api.GET("/api/v1/policies/fields")), staleTime: Infinity });
}

// El what-if no cambia nada en el servidor: no invalida ni una clave.
export function useReplayPolicy() {
  return useMutation({ mutationFn: async (body: ReplayRequest) => unwrap(await api.POST("/api/v1/policies/replay", { body })) });
}

export function useIncidents(p?: { status?: string; device_id?: string }) {
  return useQuery({
    queryKey: keys.incidents(p),
    queryFn: async () => unwrap(await api.GET("/api/v1/incidents", { params: { query: (p ?? {}) as never } })),
    refetchInterval: POLL_MS,
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: keys.incident(id),
    queryFn: async () => unwrap(await api.GET("/api/v1/incidents/{id}", { params: { path: { id } } })),
    enabled: !!id,
    refetchInterval: POLL_MS,
  });
}

export function usePatchIncident() {
  const invalidate = useInvalidate(["incidents"], keys.incidentAnalytics);
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: IncidentPatch }) =>
      unwrap(await api.PATCH("/api/v1/incidents/{id}", { params: { path: { id } }, body: patch })),
    onSuccess: invalidate,
  });
}

export function useIncidentAnalytics() {
  return useQuery({
    queryKey: keys.incidentAnalytics,
    queryFn: async () => unwrap(await api.GET("/api/v1/incidents/analytics")),
    refetchInterval: POLL_MS,
  });
}

export function useAlerts() {
  return useQuery({ queryKey: keys.alerts, queryFn: async () => unwrap(await api.GET("/api/v1/alerts")) });
}

export function useCreateAlert() {
  const invalidate = useInvalidate(keys.alerts);
  return useMutation({ mutationFn: async (body: AlertRule) => unwrap(await api.POST("/api/v1/alerts", { body })), onSuccess: invalidate });
}

export function useUpdateAlert() {
  const invalidate = useInvalidate(keys.alerts);
  return useMutation({
    mutationFn: async (body: AlertRule) => unwrap(await api.PUT("/api/v1/alerts/{id}", { params: { path: { id: body.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteAlert() {
  const invalidate = useInvalidate(keys.alerts);
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.DELETE("/api/v1/alerts/{id}", { params: { path: { id } } })),
    onSuccess: invalidate,
  });
}

// Vista previa: ni notifica ni persiste (T19), así que tampoco invalida.
export function useEvaluateAlerts() {
  return useMutation({ mutationFn: async () => unwrap(await api.POST("/api/v1/alerts/evaluate")) });
}

export function usePlaybooks() {
  return useQuery({ queryKey: keys.playbooks, queryFn: async () => unwrap(await api.GET("/api/v1/playbooks")) });
}

export function useCreatePlaybook() {
  const invalidate = useInvalidate(keys.playbooks);
  return useMutation({ mutationFn: async (body: Playbook) => unwrap(await api.POST("/api/v1/playbooks", { body })), onSuccess: invalidate });
}

export function useUpdatePlaybook() {
  const invalidate = useInvalidate(keys.playbooks);
  return useMutation({
    mutationFn: async (body: Playbook) => unwrap(await api.PUT("/api/v1/playbooks/{id}", { params: { path: { id: body.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeletePlaybook() {
  const invalidate = useInvalidate(keys.playbooks);
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.DELETE("/api/v1/playbooks/{id}", { params: { path: { id } } })),
    onSuccess: invalidate,
  });
}

export function useHandoffs(status?: string) {
  return useQuery({
    queryKey: keys.handoffs(status),
    // El query param es un enum cerrado en el esquema generado; el "Produces"
    // de esta tarea fija la firma en `string` (igual que `useIncidents`,
    // `useDevices`), así que se acota como el resto de consultas con filtro.
    queryFn: async () => unwrap(await api.GET("/api/v1/handoffs", { params: { query: (status ? { status } : {}) as never } })),
    refetchInterval: POLL_MS,
  });
}

// Aprobar ejecuta la acción pasando por los guardarraíles: cambia la bandeja,
// el registro de acciones y el estado del motor (contadores y enforcement).
export function useApproveHandoff() {
  const invalidate = useInvalidate(["handoffs"], ["actions"], keys.engine);
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note?: string }) =>
      unwrap(await api.POST("/api/v1/handoffs/{id}/approve", { params: { path: { id } }, body: { note: note ?? "" } })),
    onSuccess: invalidate,
  });
}

export function useRejectHandoff() {
  const invalidate = useInvalidate(["handoffs"]);
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note?: string }) =>
      unwrap(await api.POST("/api/v1/handoffs/{id}/reject", { params: { path: { id } }, body: { note: note ?? "" } })),
    onSuccess: invalidate,
  });
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: async () => unwrap(await api.GET("/api/v1/settings")) });
}

export function useUpdateEnforcement() {
  const invalidate = useInvalidate(keys.settings, keys.engine);
  return useMutation({
    mutationFn: async (body: EnforcementSettings) => unwrap(await api.PUT("/api/v1/settings/enforcement", { body })),
    onSuccess: invalidate,
  });
}

// El secreto de firma y el token de ntfy viajan solo aquí; el GET devuelve
// secret_set/token_set y nunca el valor (spec §5.2).
export function useUpdateWebhooks() {
  const invalidate = useInvalidate(keys.settings, keys.engine);
  return useMutation({
    mutationFn: async (body: WebhookSettings) => unwrap(await api.PUT("/api/v1/settings/webhooks", { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateEgress() {
  const invalidate = useInvalidate(keys.settings, keys.engine);
  return useMutation({
    mutationFn: async (body: EgressSettings) => unwrap(await api.PUT("/api/v1/settings/egress", { body })),
    onSuccess: invalidate,
  });
}

// Comprueba lo guardado (URL, allowlist de egress, resolución DNS) sin cuerpo.
export function useValidateSettings() {
  return useMutation({ mutationFn: async () => unwrap(await api.POST("/api/v1/settings/validate")) });
}

export function useDeviceAction() {
  const invalidate = useInvalidate(["actions"], ["devices"]);
  return useMutation({
    mutationFn: async ({ id, action, params }: { id: string; action: DeviceActionRequest["action"]; params?: Record<string, unknown> }) =>
      unwrap(await api.POST("/api/v1/devices/{id}/actions", { params: { path: { id } }, body: { action, params } as DeviceActionRequest })),
    onSuccess: invalidate,
  });
}

// Las páginas por cursor no se sondean: un refresco automático movería el
// suelo bajo una lectura paginada. placeholderData mantiene la página anterior
// mientras llega la siguiente, para que la tabla no parpadee.
export function useEventsPage(cursor?: string) {
  return useQuery({
    queryKey: keys.eventsPage(cursor),
    queryFn: async () => unwrap(await api.GET("/api/v1/events", { params: { query: cursor ? { limit: PAGE_SIZE, cursor } : { limit: PAGE_SIZE } } })),
    placeholderData: (previa) => previa,
  });
}

export function useActionsPage(cursor?: string) {
  return useQuery({
    queryKey: keys.actionsPage(cursor),
    queryFn: async () => unwrap(await api.GET("/api/v1/actions", { params: { query: cursor ? { limit: PAGE_SIZE, cursor } : { limit: PAGE_SIZE } } })),
    placeholderData: (previa) => previa,
  });
}
