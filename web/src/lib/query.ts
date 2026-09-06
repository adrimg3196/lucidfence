import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, err) => !(err instanceof ApiError && (err.status === 401 || err.status === 403 || err.status === 404)) && count < 2,
        staleTime: 5_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}
