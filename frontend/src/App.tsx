import clsx from "clsx";
import { useAtomValue } from "jotai";
import { Suspense } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

import { DownloadsSection } from "./Downloads.tsx";
import { Footer } from "./Footer.tsx";
import { LabelsSection } from "./Labels.tsx";
import { MetricsSection } from "./Metrics.tsx";
import { TimingSections } from "./Timings.tsx";
import { Toolbar } from "./Toolbar.tsx";
import { toolbarPinnedAtom } from "./atoms.ts";

export function App() {
  return (
    <main className="flex flex-col items-center">
      <h1 className="font-fancy m-8 text-center text-5xl md:text-6xl">Ma'at</h1>
      <ErrorBoundary FallbackComponent={Fallback}>
        <Suspense fallback={<Loading />}>
          <ToolbarContainer />
          <MetricsSection />
          <LabelsSection />
          <TimingSections />
          <DownloadsSection />
        </Suspense>
      </ErrorBoundary>
      <Footer className="m-8" />
    </main>
  );
}

function Loading() {
  return (
    <div className="m-10 flex justify-center">
      <div className="loading loading-infinity text-secondary loading-xl"></div>
    </div>
  );
}

function Fallback({ error }: FallbackProps) {
  return (
    <div role="alert" className="alert alert-error m-8">
      <pre>{error.message}</pre>
    </div>
  );
}

function ToolbarContainer() {
  const toolbarPinned = useAtomValue(toolbarPinnedAtom);
  return (
    <div className={clsx("flex w-full flex-col items-center", toolbarPinned && "toolbar-sticky")}>
      <nav className="toolbar-card">
        <Toolbar />
      </nav>
    </div>
  );
}
