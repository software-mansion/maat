import type { ReactNode } from "react";
import { VscInfo } from "react-icons/vsc";

export function Q({ children }: { children: ReactNode }) {
  return (
    <span className="tooltip cursor-help">
      <span className="tooltip-content">{children}</span>
      <VscInfo className="text-info inline" />
    </span>
  );
}
