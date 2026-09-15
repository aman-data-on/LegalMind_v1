"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { CheckIcon } from "lucide-react"
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"

function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        // No focus ring here: the unlayered `button:focus-visible` in globals.css
        // beats any utility and already draws LegalMind's ring (DD-22). `size-4`
        // is also the fix for the defect this replaces — `input, select, textarea
        // { width: 100% }` stretches a native checkbox, which is why the one at
        // dashboard/admin/audit renders as a wide box.
        // `p-0` is NOT cosmetic: `button` in globals.css's @layer base sets
        // `padding: .4rem .8rem`, this component declares no padding of its own,
        // and padding wider than `size-4` wins — the control renders as a wide
        // rectangle rather than a box. Every shadcn primitive built on <button>
        // needs its own padding utility here (DD-22).
        "peer size-4 shrink-0 p-0 rounded-sm border border-input outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current transition-none"
      >
        <CheckIcon className="size-3.5" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
