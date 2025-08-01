import type { ReactNode } from "react";

import type { Trend } from "./trends.ts";

export interface RichCellProps {
  value: ReactNode | null;
  href?: string | null;
  bullet?: ReactNode | null;
  trend?: Trend | null;
  rev?: string | null;
}

export function RichCell({ value, href, bullet, trend, rev }: RichCellProps) {
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
      <span className="text-base-content/60 text-xs select-none">
        <br />
        {trend && (
          <span className={trend.colorClass}>
            {trend.ratio !== 0.0 ? `${trend.symbol} ${trend.percentage}` : trend.symbol}
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
