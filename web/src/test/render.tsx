import { render } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import type { ReactNode } from "react";
import { I18nProvider, type Lang } from "@/lib/i18n";
import { createQueryClient } from "@/lib/query";

export function renderWithProviders(ui: ReactNode, opts: { route?: string; lang?: Lang } = {}) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initial={opts.lang ?? "es"}>
        <MemoryRouter initialEntries={[opts.route ?? "/"]}>{ui}</MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}
