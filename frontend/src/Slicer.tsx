import { useAtom, useAtomValue } from "jotai";
import {
  isSelected,
  pivotAtom,
  type ReportId,
  selectedSliceAtom,
  selectionAtom,
  viewModelAtom,
} from "./atoms";
import clsx from "clsx";

export function Slicer() {
  const vm = useAtomValue(viewModelAtom);
  const [selectedSlice, setSelectedSlice] = useAtom(selectedSliceAtom);

  const selection = useAtomValue(selectionAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);

  return (
    <section className="grid grid-cols-[auto_minmax(0,_1fr)] items-baseline gap-3">
      <Row title="Pivot:">
        {vm.reports.map((report, reportId) => {
          if (!isSelected(reportId, selection)) {
            return null;
          }

          return (
            <button
              key={report.title}
              className={clsx("btn btn-xs", pivot === reportId && "btn-active")}
              onClick={() => setPivot(reportId)}
            >
              {report.title}
            </button>
          );
        })}
      </Row>

      <Row title="Use a predefined slice:">
        {vm.slices.map((slice, sliceId) => {
          const isActive = "predefined" in selectedSlice && selectedSlice.predefined === sliceId;
          return (
            <button
              key={slice.title}
              className={clsx("btn btn-xs", isActive && "btn-active")}
              onClick={() => setSelectedSlice({ predefined: sliceId })}
            >
              {slice.title}
            </button>
          );
        })}
      </Row>

      <Row title="Or compose your own:">
        {vm.reports.map((report, reportId) => {
          const isActive = "custom" in selectedSlice && selectedSlice.custom.includes(reportId);
          return (
            <button
              key={report.title}
              className={clsx("btn btn-xs", isActive && "btn-active")}
              onClick={() => {
                let custom: ReportId[] = [];
                if ("custom" in selectedSlice) {
                  custom = [...selectedSlice.custom];
                }
                if (isActive) {
                  custom = custom.filter((id) => id !== reportId);
                } else {
                  custom.push(reportId);
                }
                custom.sort();
                setSelectedSlice({ custom });
              }}
            >
              {report.title}
            </button>
          );
        })}
      </Row>
    </section>
  );
}

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <aside className="text-sm text-nowrap">{title}</aside>
      <div className="flex flex-wrap gap-1">{children}</div>
    </>
  );
}
