import { Footer } from "./Footer.tsx";
import { Suspense } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { Slicer } from "./Slicer.tsx";
import { MetricsSection } from "./Metrics.tsx";
import { TimingsSection } from "./Timings.tsx";
import { DownloadsSection } from "./Downloads.tsx";

export function App() {
  return (
    <>
      <header className="flex flex-col items-center justify-center px-12 py-8">
        <h1 className="font-fancy text-5xl">Ma'at</h1>
      </header>
      <ErrorBoundary FallbackComponent={Fallback}>
        <Suspense fallback={<Loading />}>
          <main className="flex flex-col gap-4 px-4">
            <Slicer />
            <MetricsSection />
            <TimingsSection />
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
