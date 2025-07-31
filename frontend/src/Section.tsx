import type { ReactNode } from "react";
import clsx from "clsx";
import type { LabelCategory, StepName } from "./atoms.ts";
import { atomWithStorage } from "jotai/utils";
import { useAtom } from "jotai";

export type SectionId = "metrics" | `label-${LabelCategory}` | `timings-${StepName}` | "downloads";

export interface SectionProps {
  id: SectionId;
  children: ReactNode;
  className?: string;
}

export const openSectionsAtom = atomWithStorage<SectionId[] | "all">("maat-open-sections", [
  "metrics",
  "downloads",
]);

const sectionClassName = "maat-section";

export function Section({ id, children, className }: SectionProps) {
  const [opened, setOpened] = useAtom(openSectionsAtom);

  return (
    <div
      id={id}
      className={clsx(
        "collapse-arrow border-base-300 bg-base-100 collapse border",
        sectionClassName,
        className,
      )}
    >
      <input
        type="checkbox"
        checked={opened == "all" || opened.includes(id)}
        onChange={() =>
          setOpened((v) => {
            if (v == "all") {
              const sections = document.getElementsByClassName(sectionClassName);
              return Array.from(sections)
                .map((el) => el.id)
                .filter((sectionId) => sectionId !== id)
                .sort() as SectionId[];
            } else if (v.includes(id)) {
              return v.filter((x) => x !== id);
            } else {
              return [...v, id].sort();
            }
          })
        }
      />
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
