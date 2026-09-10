import { Checkbox as C } from "radix-ui";
import { Check } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

export function Checkbox({ className, ...props }: React.ComponentProps<typeof C.Root>) {
  return (
    <C.Root
      className={cn(
        "flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border border-border bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:opacity-50 data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-accent-fg",
        className,
      )}
      {...props}
    >
      <C.Indicator>
        <Check size={12} weight="bold" aria-hidden />
      </C.Indicator>
    </C.Root>
  );
}
