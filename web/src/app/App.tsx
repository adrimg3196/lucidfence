import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { I18nProvider } from "@/lib/i18n";
import { createQueryClient } from "@/lib/query";
import { ThemeProvider } from "./theme";
import { router } from "./router";

export function App() {
  const [qc] = useState(createQueryClient);
  return (
    <QueryClientProvider client={qc}>
      <I18nProvider>
        <ThemeProvider>
          <RouterProvider router={router} />
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
