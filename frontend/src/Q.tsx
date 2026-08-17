import clsx from "clsx";
import type { ReactNode } from "react";
import { VscInfo } from "react-icons/vsc";

export function Q({
  children,
  className,
  contentClassName,
}: {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <span className={clsx("tooltip cursor-help", className)}>
      <span className={clsx("tooltip-content", contentClassName)}>
        {children}
      </span>
      <VscInfo className="inline text-info" />
    </span>
  );
}
