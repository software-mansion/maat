import { useAtomValue } from "jotai";
import type { ReactNode } from "react";

import { type TimingDisplayMode, timingDisplayModeAtom } from "./atoms.ts";
import { Duration } from "./Duration.tsx";
import type { Trend } from "./trends.ts";

export interface RichCellProps {
  value: ReactNode | null;
  href?: string | null | false;
  bullet?: ReactNode | null | false;
  trend?: Trend | null | false;
  rev?: string | null | false;
}

function formatTrendChange(trend: Trend, displayMode: TimingDisplayMode): ReactNode {
  if (trend.ratio === 0.0) {
    return trend.symbol;
  }

  if (displayMode === "absolute" && trend.absoluteDiff) {
    return (
      <>
        {trend.symbol} <Duration value={trend.absoluteDiff} />
      </>
    );
  }

  return `${trend.symbol} ${trend.percentage}`;
}

export function RichCell({ value, href, bullet, trend, rev }: RichCellProps) {
  const timingDisplayMode = useAtomValue(timingDisplayModeAtom);

  if (!value) {
    return <span className="text-base-content/60">—</span>;
  }

  const before = bullet ? (
    <>
      {bullet}
      <span className="select-none"> </span>
    </>
  ) : null;

  const valueProper = href ? (
    <a href={href} className="link link-primary visited:link-secondary">
      {value}
    </a>
  ) : (
    value
  );

  const secondLine =
    trend || rev ? (
      <span className="text-base-content/60 text-xs">
        <br />
        {trend && (
          <span className={trend.colorClass}>
            {formatTrendChange(trend, timingDisplayMode)}
          </span>
        )}
        {trend && rev && " "}
        {rev && `(${rev})`}
      </span>
    ) : null;

  return (
    <>
      {before}
      {valueProper}
      {secondLine}
    </>
  );
}
