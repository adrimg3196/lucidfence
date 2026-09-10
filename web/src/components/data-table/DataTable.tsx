import type { ReactNode } from "react";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type Column<T> = { key: string; header: string; cell: (row: T) => ReactNode; className?: string };
export type EmptyState = { title: string; description?: string; action?: ReactNode };

type Props<T> = {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  empty: EmptyState;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  skeletonRows?: number;
};

// Los cuatro estados de una vista de lista, en un solo sitio (spec §11): cinco
// vistas de M2 son tablas densas y repetirlos garantizaría que alguna se dejara
// el role="alert" o el botón de reintento. El orden es deliberado: un error
// manda sobre los datos viejos que hubiera en la caché, porque enseñar una
// tabla desactualizada sin avisar es peor que no enseñar nada.
export function DataTable<T>({ columns, rows, rowKey, empty, loading = false, error = null, onRetry, skeletonRows = 5 }: Props<T>) {
  const t = useT();
  const cabecera = (
    <THead>
      <tr>
        {columns.map((c) => (
          <TH key={c.key} className={c.className}>
            {c.header}
          </TH>
        ))}
      </tr>
    </THead>
  );

  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  if (loading) {
    return (
      <div role="status" aria-label={t("state.loading")}>
        <Table>
          {cabecera}
          <TBody>
            {Array.from({ length: skeletonRows }).map((_, i) => (
              <TR key={i}>
                {columns.map((c) => (
                  <TD key={c.key} className={c.className}>
                    <Skeleton className="h-4 w-full" />
                  </TD>
                ))}
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    );
  }

  if (!rows || rows.length === 0) return <Empty title={empty.title} description={empty.description} action={empty.action} />;

  return (
    <Table>
      {cabecera}
      <TBody>
        {rows.map((row) => (
          <TR key={rowKey(row)}>
            {columns.map((c) => (
              <TD key={c.key} className={cn("whitespace-nowrap", c.className)}>
                {c.cell(row)}
              </TD>
            ))}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
