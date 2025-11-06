import { atom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import vmJson from "virtual:maat-view-model";

import { atomWithHashStorage } from "./atomWithHashStorage.ts";

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

export const Domains = {
  all: {
    name: "all",
    humanName: "All",
  },
  compiler: {
    name: "compiler",
    humanName: "Compiler",
  },
  scarb: {
    name: "scarb",
    humanName: "Scarb",
  },
  forge: {
    name: "forge",
    humanName: "Forge",
  },
  lint: {
    name: "lint",
    humanName: "Lint",
  },
  ls: {
    name: "ls",
    humanName: "LS",
  },
} as const;

export type DomainName = keyof typeof Domains;

export function isDomainName(value: string): value is DomainName {
  return value in Domains;
}

export interface StepReport {
  name: string;
  executionTime: string | null;
  exitCode: number | null;
}

export type TestRunner = "snforge" | "cairo-test";

export interface Test {
  name: TestName;
  rev: string;
  labels: Label[];
  logsHref: string;
  testRunner: TestRunner | null;
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

  isReportTitle(value: string): value is ReportTitle {
    return value in vm.reports;
  },

  isSliceTitle(value: string): value is SliceTitle {
    return value in vm.slices;
  },
} as const;

export function urlOf(viewModelUrl: string): string {
  return `${import.meta.env.BASE_URL}/${viewModelUrl}`;
}

export type SelectedSlice = { predefined: SliceTitle } | { custom: ReportTitle[] };

export const selectedSliceAtom = atomWithHashStorage<SelectedSlice>({
  key: "s",
  getDefault() {
    const defaultSlice = Object.values(vm.slices).find((slice) => slice.default);
    if (defaultSlice) {
      return { predefined: defaultSlice.title };
    } else {
      return { custom: [] };
    }
  },
  serialize(value) {
    if ("predefined" in value) {
      return `*${value.predefined}`;
    } else {
      return value.custom.join(" ");
    }
  },
  deserialize(value) {
    if (value.startsWith("*")) {
      const predefined = value.slice(1);
      if (!vm.isSliceTitle(predefined)) {
        throw new Error("selectedSliceAtom: invalid predefined value");
      }
      return { predefined: predefined };
    } else {
      return {
        custom: value.split(" ").filter((title) => vm.isReportTitle(title)),
      };
    }
  },
});

export const selectionAtom = atom<ReportTitle[]>((get) => {
  const selectedSlice = get(selectedSliceAtom);
  if ("predefined" in selectedSlice) {
    return vm.slice(selectedSlice.predefined).reports;
  } else {
    return selectedSlice.custom;
  }
});

export const selectedReportsAtom = atom<Report[]>((get) =>
  get(selectionAtom)
    .map((title) => vm.report(title))
    .filter(Boolean),
);

export const pivotAtom = atomWithHashStorage<ReportTitle | undefined>({
  key: "p",
  getDefault: (get) => get(selectionAtom)[0],
  serialize: (value) => value,
  deserialize(value) {
    if (vm.isReportTitle(value)) {
      return value;
    } else {
      throw new Error("pivotAtom: invalid value");
    }
  },
});

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

export const selectedDomainNameAtom = atomWithHashStorage<DomainName>({
  key: "d",
  getDefault: () => "all",
  serialize: (value) => value,
  deserialize(value) {
    if (isDomainName(value)) {
      return value;
    } else {
      throw new Error("domainAtom: invalid value");
    }
  },
});

export function showSectionInDomain(sectionId: SectionId, domainName: DomainName): boolean {
  const when = (...domains: DomainName[]) => domainName === "all" || domains.includes(domainName);
  switch (sectionId) {
    case "metrics":
      return true;
    case "label-error":
      return when("scarb");
    case "label-build-fail":
      return when("compiler", "scarb");
    case "label-test-error":
      return when("forge");
    case "label-test-fail":
      return when("forge");
    case "label-test-pass":
      return when();
    case "label-lint-fail":
      return when("lint");
    case "label-ls-fail":
      return when("ls");
    case "label-broken":
      return when("scarb");
    case "label-lint-broken":
      return when("lint");
    case "label-ls-broken":
      return when("ls");
    case "timings-build":
      return when("compiler", "scarb");
    case "timings-lint":
      return when("lint");
    case "timings-test":
      return when("forge");
    case "timings-ls":
      return when("ls");
    case "downloads":
      return true;
  }
}

export function useShowSectionInSelectedDomain(sectionId: SectionId): boolean {
  const selectedDomainName = useAtomValue(selectedDomainNameAtom);
  return showSectionInDomain(sectionId, selectedDomainName);
}
