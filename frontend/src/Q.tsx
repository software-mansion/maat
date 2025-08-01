import type { ReactNode } from "react";

export function Q({ children }: { children: ReactNode }) {
  return (
    <span className="tooltip badge badge-xs badge-dash cursor-help select-none">
      <span className="tooltip-content">{children}</span>?
    </span>
  );
}
