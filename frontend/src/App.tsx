import { Footer } from "./Footer.tsx";
import { Navbar } from "./Navbar.tsx";
import { Suspense } from "react";

export function App() {
  return (
    <>
      <Navbar />
      <Suspense fallback={<Loading />}></Suspense>
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
