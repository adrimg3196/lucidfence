import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      neutral: "border-border bg-bg-2 text-fg-2",
      success: "border-transparent bg-sev-low/15 text-sev-low",
      warning: "border-transparent bg-sev-medium/15 text-sev-medium",
      danger: "border-transparent bg-sev-high/15 text-sev-high",
      info: "border-transparent bg-info/15 text-info",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
