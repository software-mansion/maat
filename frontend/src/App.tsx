import { Footer } from "./Footer.tsx";
import { Suspense } from "react";
import { viewModelAtom } from "./atoms.ts";
import { useAtomValue } from "jotai";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

export function App() {
  return (
    <>
      <header className="flex flex-col items-center justify-center px-12 py-8">
        <h1 className="font-fancy text-5xl">Ma'at</h1>
      </header>
      <ErrorBoundary FallbackComponent={Fallback}>
        <Suspense fallback={<Loading />}>
          <main className="flex flex-col gap-4 px-4">
            <PreviewViewModel />
            <div className="collapse-arrow border-base-300 bg-base-100 collapse overflow-hidden border">
              <input type="checkbox" />
              <div className="collapse-title font-bold select-none">Downloads</div>
              <table className="collapse-content table-pin-rows table-pin-cols table">
                <thead>
                  <tr>
                    <th>Data exports</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th>Ecosystem (CSV)</th>
                  </tr>
                  <tr>
                    <th>Ecosystem (JSON)</th>
                  </tr>
                </tbody>
              </table>
            </div>
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

function PreviewViewModel() {
  const viewModel = useAtomValue(viewModelAtom);
  return <pre>{`${JSON.stringify(viewModel, null, 2)}`}</pre>;
}
