import { atom, useAtomValue } from "jotai";
import { atomWithDefault, unwrap } from "jotai/utils";

export type SliceId = number;
export type ReportId = number;

export interface Metrics {
  workspace: string;
  scarbVersion: string;
  foundryVersion: string;
  maatCommit: string;
  createdAt: string;
  totalExecutionTime: string;
  totalProjects: number;
  meanBuildTime: string | null;
  meanLintTime: string | null;
  meanTestTime: string | null;
  meanLsTime: string | null;
  medianBuildTime: string | null;
  medianLintTime: string | null;
  medianTestTime: string | null;
  medianLsTime: string | null;
}

export interface Report {
  title: string;
  ecosystemCsvHref: string;
  ecosystemJsonHref: string;
  metrics: Metrics;
}

export interface Slice {
  title: string;
  reportIds: ReportId[];
  default?: boolean;
}

export interface Trend {
  ratio: number;
  isExtreme: boolean;
  symbol: string;
  percentage: string;
  colorClass: string;
}

export interface ViewModel {
  reports: Report[];
  slices: Slice[];
}

export function urlOf(viewModelUrl: string): string {
  return import.meta.env.DEV ? `vm-dev/${viewModelUrl}` : viewModelUrl;
}

export const viewModelAtom = atom<Promise<ViewModel>>(async (_get, { signal }) => {
  const response = await fetch(urlOf("vm.json"), { signal });
  return response.json();
});

const unwrappedViewModelAtom = unwrap(viewModelAtom);

export type SelectedSlice = { predefined: SliceId } | { custom: ReportId[] };

export const selectedSliceAtom = atomWithDefault<SelectedSlice>((get) => {
  const vm = get(unwrappedViewModelAtom);
  if (!vm) {
    return { custom: [] };
  }

  const predefined = vm.slices.findIndex((slice) => slice.default);
  if (predefined >= 0) {
    return { predefined };
  } else {
    return { custom: [] };
  }
});

export const selectionAtom = atom<ReportId[]>((get) => {
  const selectedSlice = get(selectedSliceAtom);
  if ("predefined" in selectedSlice) {
    const vm = get(unwrappedViewModelAtom);
    if (!vm) {
      return [];
    } else {
      return vm.slices[selectedSlice.predefined].reportIds;
    }
  } else {
    return selectedSlice.custom;
  }
});

export function isSelected(itemId: number, selection: number[]) {
  return selection.includes(itemId);
}

export function applySelection<T>(values: T[], selection: number[]): T[] {
  return values.filter((_, i) => isSelected(i, selection));
}

export const pivotAtom = atomWithDefault<ReportId>((get) => {
  const selection = get(selectionAtom);
  return selection.length > 0 ? selection[0] : 0;
});

export function useReportById(reportId: ReportId): Report {
  const vm = useAtomValue(viewModelAtom);
  return vm.reports[reportId];
}
