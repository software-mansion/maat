import { useAtom, useAtomValue } from "jotai";
import {
  pivotAtom,
  type ReportTitle,
  selectedReportsAtom,
  selectedSliceAtom,
  viewModelAtom,
} from "./atoms";
import type { ReactNode } from "react";
import { openSectionsAtom } from "./Section.tsx";
import { VscFold, VscUnfold } from "react-icons/vsc";

export function Toolbar() {
  const vm = useAtomValue(viewModelAtom);
  const [selectedSlice, setSelectedSlice] = useAtom(selectedSliceAtom);
  const selectedReports = useAtomValue(selectedReportsAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);

  return (
    <form className="grid auto-rows-auto grid-cols-[auto_minmax(0,1fr)_auto] items-baseline gap-3">
      <Fieldset title="Pivot:">
        {selectedReports.map((report) => (
          <input
            key={report.title}
            type="radio"
            name="pivot"
            className="btn btn-xs"
            aria-label={report.title}
            checked={pivot === report.title}
            onChange={() => setPivot(report.title)}
          />
        ))}
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

      <div className="col-start-3 row-start-1 row-end-4 flex flex-col gap-3">
        <ToggleSectionsButton />
      </div>
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

function ToggleSectionsButton() {
  const [openSections, setOpenSections] = useAtom(openSectionsAtom);
  const areSectionsClosed = openSections instanceof Array && openSections.length == 0;
  return (
    <button
      className="btn btn-sm tooltip tooltip-left"
      data-tip={areSectionsClosed ? "Open all sections" : "Close all sections"}
      onClick={(e) => {
        e.preventDefault();
        setOpenSections(areSectionsClosed ? "all" : []);
      }}
    >
      {areSectionsClosed ? (
        <VscUnfold className="size-[1.2em]" />
      ) : (
        <VscFold className="size-[1.2em]" />
      )}
    </button>
  );
}
