import { Switch as S } from "radix-ui";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: React.ComponentProps<typeof S.Root>) {
  return (
    <S.Root
      className={cn(
        "inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-border bg-bg-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:opacity-50 data-[state=checked]:border-accent data-[state=checked]:bg-accent",
        className,
      )}
      {...props}
    >
      <S.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-panel shadow-sm transition-transform data-[state=checked]:translate-x-[18px]" />
    </S.Root>
  );
}
