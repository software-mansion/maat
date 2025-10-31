import clsx from "clsx";
import { useAtom } from "jotai";
import { VscLinkExternal } from "react-icons/vsc";

import { Domains, selectedDomainNameAtom } from "./atoms.ts";

export function Tabs({ className }: { className?: string }) {
  const [selectedDomainName, setSelectedDomainName] = useAtom(selectedDomainNameAtom);
  return (
    <div role="tablist" className={clsx("tabs tabs-border", className)}>
      {Object.values(Domains).map((domain) => (
        <a
          key={domain.name}
          role="tab"
          className={clsx("tab", domain.name === selectedDomainName && "tab-active")}
          onClick={() => setSelectedDomainName(domain.name)}
        >
          {domain.humanName}
        </a>
      ))}
      <a
        role="tab"
        className="tab"
        href="https://github.com/software-mansion/maat/actions/workflows/experiment.yml"
        rel="noopener noreferrer"
        target="_blank"
      >
        Queue&nbsp;
        <VscLinkExternal className="inline size-3" />
      </a>
      <a
        role="tab"
        className="tab"
        href="https://github.com/software-mansion/maat/tree/main/docs"
        rel="noopener noreferrer"
        target="_blank"
      >
        Docs&nbsp;
        <VscLinkExternal className="inline size-3" />
      </a>
    </div>
  );
}
