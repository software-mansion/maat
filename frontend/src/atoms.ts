import { atom } from "jotai";
import { atomWithDefault, unwrap } from "jotai/utils";

// NOTE: These types in reality are just strings that come from JSON.parse call,
//   but for extra type safety a fake unique symbol tag is used to prevent TypeScript
//   from structural type matching.
export type ReportTitle = string & { readonly __nonexistent_tag: unique symbol };
export type SliceTitle = string & { readonly __nonexistent_tag: unique symbol };

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
  title: ReportTitle;
  ecosystemCsvHref: string;
  ecosystemJsonHref: string;
  metrics: Metrics;
}

export interface Slice {
  title: SliceTitle;
  reports: ReportTitle[];
  default?: boolean;
}

export interface ViewModel {
  reports: Record<ReportTitle, Report>;
  slices: Record<SliceTitle, Slice>;
}

export function urlOf(viewModelUrl: string): string {
  return import.meta.env.DEV ? `vm-dev/${viewModelUrl}` : viewModelUrl;
}

export const viewModelAtom = atom<Promise<ViewModel>>(async (_get, { signal }) => {
  const response = await fetch(urlOf("vm.json"), { signal });
  return response.json();
});

const unwrappedViewModelAtom = unwrap(viewModelAtom);

export type SelectedSlice = { predefined: SliceTitle } | { custom: ReportTitle[] };

export const selectedSliceAtom = atomWithDefault<SelectedSlice>((get) => {
  const vm = get(unwrappedViewModelAtom);
  if (!vm) {
    return { custom: [] };
  }

  const defaultSlice = Object.values(vm.slices).find((slice) => slice.default);
  if (defaultSlice) {
    return { predefined: defaultSlice.title };
  } else {
    return { custom: [] };
  }
});

export const selectionAtom = atom<ReportTitle[]>((get) => {
  const selectedSlice = get(selectedSliceAtom);
  if ("predefined" in selectedSlice) {
    const vm = get(unwrappedViewModelAtom);
    if (!vm) {
      return [];
    } else {
      return vm.slices[selectedSlice.predefined].reports;
    }
  } else {
    return selectedSlice.custom;
  }
});

export function isSelected(itemTitle: string, selection: string[]) {
  return selection.includes(itemTitle);
}

export function applySelection<T>(values: Record<string, T>, selection: string[]): T[] {
  return selection.map((title) => values[title]).filter(Boolean);
}

export const pivotAtom = atomWithDefault<ReportTitle>((get) => {
  const [first] = get(selectionAtom);
  return first;
});
