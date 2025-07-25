import { atom } from "jotai";

export const viewModelAtom = atom(async (_get, { signal }) => {
  const vmUrl = import.meta.env.DEV ? "vm-dev/vm.json" : "vm.json";
  const response = await fetch(vmUrl, { signal });
  return await response.json();
});
