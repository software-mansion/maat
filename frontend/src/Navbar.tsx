import { Suspense } from "react";

export function Navbar() {
  return (
    <header className="flex flex-col items-center justify-center px-12 py-8">
      <h1 className="font-fancy text-5xl">Ma'at</h1>
      <Suspense fallback={<></>}></Suspense>
    </header>
  );
}
