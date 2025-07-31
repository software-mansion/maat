import clsx from "clsx";
import { useAtomValue } from "jotai";

import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow } from "./Table.tsx";
import {
  type Label,
  type LabelCategory,
  type Report,
  type ReportTitle,
  type Test,
  type TestName,
  type ViewModel,
  pivotReportAtom,
  selectionAtom,
  urlOf,
  viewModelAtom,
} from "./atoms.ts";
import { determineUniformRevForTest } from "./utils.ts";

const colors: Record<"border" | "text", Record<LabelCategory, string>> = {
  border: {
    error: "border-red-500",
    "build-fail": "border-orange-500",
    "test-error": "border-yellow-500",
    "test-fail": "border-blue-500",
    "test-pass": "border-green-500",
    "lint-fail": "border-purple-500",
    "ls-fail": "border-pink-500",
    broken: "border-slate-500",
    "lint-broken": "border-purple-300",
    "ls-broken": "border-pink-300",
  },
  text: {
    error: "text-red-500",
    "build-fail": "text-orange-500",
    "test-error": "text-yellow-500",
    "test-fail": "text-blue-500",
    "test-pass": "text-green-500",
    "lint-fail": "text-purple-500",
    "ls-fail": "text-pink-500",
    broken: "text-slate-500",
    "lint-broken": "text-purple-300",
    "ls-broken": "text-pink-300",
  },
} as const;

interface Group {
  category: LabelCategory;
  count: number;
  ratio: number;
  rows: Row[];
}

interface Row {
  testName: string;
  cells: Record<ReportTitle, Cell>;
  uniformRev?: string;
}

const Missing = Symbol("Missing");

type Cell =
  | {
      label: Label;
      logsHref: string;
      rev?: string;
    }
  | typeof Missing;

export function LabelsSection() {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);
  const pivot = useAtomValue(pivotReportAtom);

  const labelGroups = Array.from(buildLabelGroups(vm, selection, pivot));

  return (
    <>
      {labelGroups.map((group) => (
        <LabelGroupSection key={group.category} group={group} />
      ))}
    </>
  );
}

function LabelGroupSection({ group }: { group: Group }) {
  return (
    <Section id={`label-${group.category}`} className={clsx(colors.border[group.category])}>
      <SectionTitle>
        <LabelCategoryBullet category={group.category} />
        {` ${group.category} `}
        <span className="text-base-content/60 font-normal">
          ({group.count}, {(group.ratio * 100).toFixed(2)}%)
        </span>
      </SectionTitle>
      <SectionTable>
        <ReportTableHead title="Project" />
        <tbody>
          {group.rows.map((project) => (
            <ReportTableRow
              key={project.testName}
              title={
                <>
                  {project.testName}
                  {project.uniformRev && (
                    <span className="text-base-content/60 font-normal">{` (${project.uniformRev})`}</span>
                  )}
                </>
              }
              textAlign="center"
              cell={(report) => <LabelCell cell={project.cells[report.title]} />}
            />
          ))}
        </tbody>
      </SectionTable>
    </Section>
  );
}

function LabelCell({ cell }: { cell: Cell }) {
  if (cell == Missing) {
    return <span className="text-base-content/60">—</span>;
  }

  const { label, logsHref, rev } = cell;

  return (
    <>
      <LabelCategoryBullet category={label.category} />
      <span className="select-none"> </span>
      <a href={urlOf(logsHref)} className="link link-primary visited:link-secondary">
        {label.comment || label.category}
      </a>
      {rev && (
        <>
          <br />
          <span className="text-base-content/60 text-sm">({rev})</span>
        </>
      )}
    </>
  );
}

function LabelCategoryBullet({ category }: { category: LabelCategory }) {
  return (
    <span
      aria-label={category}
      data-tip={category}
      className={clsx(
        "tooltip cursor-help font-normal no-underline select-none",
        colors.text[category],
      )}
    >
      ❖
    </span>
  );
}

function* buildLabelGroups(
  vm: ViewModel,
  selection: ReportTitle[],
  pivot: Report | undefined,
): Generator<Group> {
  if (pivot == undefined) {
    return;
  }

  // For each category, build the label group.
  for (const category of vm.labelCategories) {
    // Find all tests that have this category in the pivot report (not missing).
    const testsInThisCategory: TestName[] = sortedUnique(
      (function* () {
        for (const test of pivot.tests) {
          if (test.labels.some((label: Label) => label.category === category)) {
            yield test.name;
          }
        }
      })(),
    );

    // Don't produce empty groups.
    if (testsInThisCategory.length === 0) {
      continue;
    }

    // For each project with this category, build cells for all reports.
    const rows: Row[] = testsInThisCategory.map((testName) => {
      const uniformRev = determineUniformRevForTest(vm, selection, testName);

      return {
        testName,
        cells: Object.fromEntries(
          (function* () {
            for (const reportTitle of selection) {
              const report = vm.reports[reportTitle];
              const test = report?.tests?.find((t: Test) => t.name === testName);
              const label: Label | undefined = prioritize(test?.labels ?? [], category)[0];
              if (test && label) {
                yield [
                  reportTitle,
                  {
                    label,
                    logsHref: test.logsHref,
                    // Only provide test rev if we have no uniformRev.
                    rev: uniformRev ? undefined : test.rev,
                  } as const,
                ];
              } else {
                yield [reportTitle, Missing];
              }
            }
          })(),
        ),
        uniformRev,
      };
    });

    yield {
      category,
      count: testsInThisCategory.length,
      ratio: testsInThisCategory.length / pivot.tests.length,
      rows,
    };
  }
}

/** Prioritise labels: first try to find the specified category, then fall back to any label. */
function prioritize(labels: Label[], category: LabelCategory): Label[] {
  return labels.toSorted(
    (a, b) => Number(b.category === category) - Number(a.category === category),
  );
}

function sortedUnique<T>(values: Iterable<T>): T[] {
  return [...new Set(values)].sort();
}
