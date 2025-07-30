import type { ReactNode } from "react";
import clsx from "clsx";
import type { LabelCategory, StepName } from "./atoms.ts";

export type SectionId = "metrics" | `label-${LabelCategory}` | `timings-${StepName}` | "downloads";

export interface SectionProps {
  id: SectionId;
  children: ReactNode;
  className?: string;
  defaultOpen?: boolean;
}

export function Section({ id, children, className, defaultOpen = false }: SectionProps) {
  return (
    <div
      id={id}
      className={clsx("collapse-arrow border-base-300 bg-base-100 collapse border", className)}
    >
      <input type="checkbox" defaultChecked={defaultOpen} />
      {children}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="collapse-title font-bold select-none">{children}</div>;
}

export function SectionContent({ children }: { children: ReactNode }) {
  return <div className="collapse-content overflow-x-auto p-0">{children}</div>;
}

export function SectionTable({ children }: { children: ReactNode }) {
  return (
    <SectionContent>
      <table className="table-pin-cols table-pin-rows table">{children}</table>
    </SectionContent>
  );
}
