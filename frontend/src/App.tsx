import clsx from "clsx";
import { useAtomValue } from "jotai";
import { Suspense } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { toolbarPinnedAtom } from "./atoms.ts";
import { DownloadsSection } from "./Downloads.tsx";
import { Footer } from "./Footer.tsx";
import { LabelsSection } from "./Labels.tsx";
import { MetricsSection } from "./Metrics.tsx";
import { Tabs } from "./Tabs.tsx";
import { TimingSections } from "./Timings.tsx";
import { Toolbar } from "./Toolbar.tsx";

export function App() {
  return (
    <main className="flex flex-col items-center">
      <Header />
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
      <div className="loading loading-infinity loading-xl text-secondary"></div>
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

function Header() {
  const toolbarPinned = useAtomValue(toolbarPinnedAtom);
  return (
    <a
      href="#root"
      className={clsx(
        "z-11 w-full p-8 text-center font-fancy text-5xl md:text-6xl",
        toolbarPinned && "bg-base-100",
      )}
    >
      <h1>Ma'at</h1>
    </a>
  );
}

function ToolbarContainer() {
  const toolbarPinned = useAtomValue(toolbarPinnedAtom);
  return (
    <div
      className={clsx(
        "flex w-full flex-col items-center",
        toolbarPinned && "sticky top-0 z-10",
      )}
    >
      <nav
        className={clsx(
          "toolbar-card mx-4 flex flex-col items-center rounded-(--radius-box) border border-base-300 bg-base-100",
          toolbarPinned &&
            "w-full rounded-none border-x-base-100 border-t-base-100 px-4",
        )}
      >
        <Toolbar className="m-4 max-w-5xl" />
        <Tabs />
      </nav>
    </div>
  );
}
