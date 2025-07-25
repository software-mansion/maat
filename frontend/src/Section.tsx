import type { ReactNode } from "react";

export interface SectionProps {
  children: ReactNode;
  defaultOpen?: boolean;
}

export function Section({ children, defaultOpen = false }: SectionProps) {
  return (
    <div className="collapse-arrow border-base-300 bg-base-100 collapse border">
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
