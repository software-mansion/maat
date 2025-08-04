import { atom } from "jotai";
import { atomWithDefault, atomWithStorage } from "jotai/utils";
import vmJson from "virtual:maat-view-model";

// NOTE: These types in reality are just strings that come from JSON.parse call,
//   but for extra type safety a fake unique symbol tag is used to prevent TypeScript
//   from structural type matching.
export type ReportTitle = string & { readonly __nonexistent_tag: unique symbol };
export type SliceTitle = string & { readonly __nonexistent_tag: unique symbol };
export type TestName = string & { readonly __nonexistent_tag: unique symbol };

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

export type LabelCategory =
  | "error"
  | "build-fail"
  | "test-error"
  | "test-fail"
  | "test-pass"
  | "lint-fail"
  | "ls-fail"
  | "broken"
  | "lint-broken"
  | "ls-broken";

export interface Label {
  category: LabelCategory;
  comment: string | null;
}

export const Steps = {
  build: {
    humanName: "Build",
    meanKey: "meanBuildTime",
    medianKey: "medianBuildTime",
  },
  lint: {
    humanName: "Lint",
    meanKey: "meanLintTime",
    medianKey: "medianLintTime",
  },
  test: {
    humanName: "Test",
    meanKey: "meanTestTime",
    medianKey: "medianTestTime",
  },
  ls: {
    humanName: "LS",
    meanKey: "meanLsTime",
    medianKey: "medianLsTime",
  },
} as const;

export type StepName = keyof typeof Steps;

export interface StepReport {
  name: string;
  executionTime: string | null;
  exitCode: number | null;
}

export interface Test {
  name: TestName;
  rev: string;
  labels: Label[];
  logsHref: string;
  build: StepReport | null;
  test: StepReport | null;
  lint: StepReport | null;
  ls: StepReport | null;
}

export interface Report {
  title: ReportTitle;
  ecosystemCsvHref: string;
  ecosystemJsonHref: string;
  metrics: Metrics;
  tests: Test[];
}

export interface Slice {
  title: SliceTitle;
  reports: ReportTitle[];
  default?: boolean;
}

export interface ViewModel {
  reports: Record<ReportTitle, Report>;
  slices: Record<SliceTitle, Slice>;
  labelCategories: LabelCategory[];
}

export const vm = {
  ...(vmJson as ViewModel),

  /** Type-safe report access. */
  report(title: ReportTitle): Report {
    return vm.reports[title]!;
  },

  /** Type-safe slice access. */
  slice(title: SliceTitle): Slice {
    return vm.slices[title]!;
  },
} as const;

export function urlOf(viewModelUrl: string): string {
  return `${import.meta.env.BASE_URL}/${viewModelUrl}`;
}

export type SelectedSlice = { predefined: SliceTitle } | { custom: ReportTitle[] };

export const selectedSliceAtom = atomWithDefault<SelectedSlice>(() => {
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
    return vm.slice(selectedSlice.predefined).reports;
  } else {
    return selectedSlice.custom;
  }
});

export const selectedReportsAtom = atom<Report[]>((get) => {
  return get(selectionAtom)
    .map((title) => vm.report(title))
    .filter(Boolean);
});

export const pivotAtom = atomWithDefault<ReportTitle | undefined>((get) => get(selectionAtom)[0]);

export const pivotReportAtom = atom<Report | undefined>((get) => {
  const pivot = get(pivotAtom);
  if (!pivot) {
    return undefined;
  } else {
    return vm.reports[pivot];
  }
});

export type SectionId = "metrics" | `label-${LabelCategory}` | `timings-${StepName}` | "downloads";

export const openSectionsAtom = atomWithStorage<SectionId[] | "all">("maat-open-sections", [
  "metrics",
  "downloads",
]);

export const toolbarPinnedAtom = atomWithStorage<boolean>("maat-toolbar-pinned", true);
