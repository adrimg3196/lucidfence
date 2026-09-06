import createClient from "openapi-fetch";
import type { paths } from "./schema";

let csrf = "";

export function setCsrf(value: string) {
  csrf = value;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const api = createClient<paths>({ baseUrl: "/", credentials: "same-origin" });

api.use({
  onRequest({ request }) {
    if (csrf && request.method !== "GET" && request.method !== "HEAD") request.headers.set("X-LucidFence-CSRF", csrf);
    return request;
  },
});

type Result<T> = { data?: T; error?: unknown; response: Response };

export function unwrap<T>(res: Result<T>): T {
  if (res.response.ok) return res.data as T;
  const err = (res.error ?? {}) as { error?: string; code?: string; detail?: unknown };
  throw new ApiError(res.response.status, err.code ?? "unknown", err.error ?? `HTTP ${res.response.status}`, err.detail);
}
