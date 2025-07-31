import { Suspense } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

import { DownloadsSection } from "./Downloads.tsx";
import { Footer } from "./Footer.tsx";
import { LabelsSection } from "./Labels.tsx";
import { MetricsSection } from "./Metrics.tsx";
import { TimingSections } from "./Timings.tsx";
import { Toolbar } from "./Toolbar.tsx";

export function App() {
  return (
    <>
      <header className="flex flex-col items-center justify-center px-12 py-8">
        <h1 className="font-fancy text-5xl">Ma'at</h1>
      </header>
      <ErrorBoundary FallbackComponent={Fallback}>
        <Suspense fallback={<Loading />}>
          <main className="flex flex-col gap-4 px-4">
            <Toolbar />
            <MetricsSection />
            <LabelsSection />
            <TimingSections />
            <DownloadsSection />
          </main>
        </Suspense>
      </ErrorBoundary>
      <Footer />
    </>
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
