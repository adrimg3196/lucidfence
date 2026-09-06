import { Tabs as T } from "radix-ui";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;
export function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return <T.List className={cn("inline-flex gap-1 rounded-[var(--radius-ui)] border border-border bg-bg-2 p-1", className)} {...props} />;
}
export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn("rounded-[6px] px-3 py-1.5 text-sm text-fg-2 data-[state=active]:bg-panel data-[state=active]:text-fg data-[state=active]:shadow-sm", className)}
      {...props}
    />
  );
}
export const TabsContent = T.Content;
