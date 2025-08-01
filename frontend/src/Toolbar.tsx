import clsx from "clsx";
import { useAtom, useAtomValue } from "jotai";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { VscFold, VscPin, VscUnfold } from "react-icons/vsc";

import {
  type ReportTitle,
  openSectionsAtom,
  pivotAtom,
  selectedReportsAtom,
  selectedSliceAtom,
  toolbarPinnedAtom,
  viewModelAtom,
} from "./atoms";

export function Toolbar() {
  const vm = useAtomValue(viewModelAtom);
  const [selectedSlice, setSelectedSlice] = useAtom(selectedSliceAtom);
  const selectedReports = useAtomValue(selectedReportsAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);

  return (
    <form className="grid max-w-5xl auto-rows-auto grid-cols-1 gap-3 md:grid-cols-[auto_minmax(0,1fr)_auto]">
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

      <div className="flex gap-3 md:col-start-3 md:row-start-1 md:row-end-4 md:flex-col">
        <PinToolbarButton />
        <ToggleSectionsButton />
      </div>
    </form>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="contents">
      <legend className="self-baseline text-sm text-nowrap">{title}</legend>
      <div className="flex flex-wrap gap-1 self-baseline">{children}</div>
    </fieldset>
  );
}

function ToggleSectionsButton() {
  const [openSections, setOpenSections] = useAtom(openSectionsAtom);
  const areSectionsClosed = openSections instanceof Array && openSections.length == 0;
  return (
    <ToolButton
      label={areSectionsClosed ? "Open all sections" : "Close all sections"}
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
    </ToolButton>
  );
}

function PinToolbarButton() {
  const [toolbarPinned, setToolbarPinned] = useAtom(toolbarPinnedAtom);
  return (
    <ToolButton
      label={`${toolbarPinned ? "Unpin" : "Pin"} toolbar`}
      active={toolbarPinned}
      onClick={(e) => {
        e.preventDefault();
        setToolbarPinned(!toolbarPinned);
      }}
    >
      <VscPin className="size-[1.2em]" />
    </ToolButton>
  );
}

interface ToolButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  active?: boolean;
  children: ReactNode;
}

function ToolButton({ label, active, children, ...props }: ToolButtonProps) {
  return (
    <button
      {...props}
      className={clsx("btn btn-sm md:tooltip md:tooltip-left", active === true && "btn-active")}
      data-tip={label}
    >
      {children}
      <span className="md:hidden">{label}</span>
    </button>
  );
}
