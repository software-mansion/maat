import { Footer } from "./Footer.tsx";
import { Navbar } from "./Navbar.tsx";
import { Suspense } from "react";
import { viewModelAtom } from "./atoms.ts";
import { useAtomValue } from "jotai";

export function App() {
  return (
    <>
      <Navbar />
      <Suspense fallback={<Loading />}>
        <PreviewViewModel />
      </Suspense>
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

function PreviewViewModel() {
  const viewModel = useAtomValue(viewModelAtom);
  return <pre>{`${JSON.stringify(viewModel, null, 2)}`}</pre>;
}
