import { useAtom, useAtomValue } from "jotai";
import {
  isSelected,
  pivotAtom,
  type ReportTitle,
  selectedSliceAtom,
  selectionAtom,
  viewModelAtom,
} from "./atoms";
import type { ReactNode } from "react";

export function Slicer() {
  const vm = useAtomValue(viewModelAtom);
  const [selectedSlice, setSelectedSlice] = useAtom(selectedSliceAtom);

  const selection = useAtomValue(selectionAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);

  return (
    <form className="grid grid-cols-[auto_minmax(0,_1fr)] items-baseline gap-3">
      <Fieldset title="Pivot:">
        {Object.values(vm.reports).map((report) => {
          if (!isSelected(report.title, selection)) {
            return null;
          }

          return (
            <input
              key={report.title}
              type="radio"
              name="pivot"
              className="btn btn-xs"
              aria-label={report.title}
              checked={pivot === report.title}
              onChange={() => setPivot(report.title)}
            />
          );
        })}
      </Fieldset>

      <Fieldset title="Use a predefined slice:">
        {Object.values(vm.slices).map((slice) => {
          const isActive =
            "predefined" in selectedSlice && selectedSlice.predefined === slice.title;
          return (
            <input
              key={slice.title}
              type="radio"
              name="predefined-slice"
              className="btn btn-xs"
              aria-label={slice.title}
              checked={isActive}
              onChange={() => setSelectedSlice({ predefined: slice.title })}
            />
          );
        })}
      </Fieldset>

      <Fieldset title="Or compose your own:">
        {Object.values(vm.reports).map((report) => {
          const isActive = "custom" in selectedSlice && selectedSlice.custom.includes(report.title);
          return (
            <input
              key={report.title}
              type="checkbox"
              name="custom-slice"
              className="btn btn-xs"
              aria-label={report.title}
              checked={isActive}
              onChange={() => {
                let custom: ReportTitle[] = [];
                if ("custom" in selectedSlice) {
                  custom = [...selectedSlice.custom];
                }
                if (isActive) {
                  custom = custom.filter((title) => title !== report.title);
                } else {
                  custom.push(report.title);
                }
                custom.sort();
                setSelectedSlice({ custom });
              }}
            />
          );
        })}
      </Fieldset>
    </form>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="contents">
      <legend className="text-sm text-nowrap">{title}</legend>
      <div className="flex flex-wrap gap-1">{children}</div>
    </fieldset>
  );
}
