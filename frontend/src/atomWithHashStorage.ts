import { atom } from "jotai";
import { atomWithHash } from "jotai-location";
import type { SetStateAction, WritableAtom } from "jotai/vanilla";
import { RESET } from "jotai/vanilla/utils";

type Options<Value> = {
  key: string;
  getDefault: WritableAtom<Value, [SetStateAction<Value> | typeof RESET], void>["read"];
  serialize: (value: NonNullable<Value>) => string;
  deserialize: (str: string) => Value;
};

export function atomWithHashStorage<Value>({
  key,
  getDefault,
  serialize,
  deserialize,
}: Options<Value>): WritableAtom<Value, [SetStateAction<Value> | typeof RESET], void> {
  // NOTE: We use RESET as a "default" field placeholder to abuse its special treatment when setting atom value.
  //   Thanks to this, setting the hash to "default" makes it actually disappear from the window location.
  const hashAtom = atomWithHash<Value | typeof RESET>(key, RESET, {
    serialize(value) {
      if (value === RESET) {
        throw new Error("RESET should never be serialized");
      } else if (value == null) {
        throw new Error("null/undefined should never be serialized if nullIsReset is true");
      } else {
        return serialize(value);
      }
    },

    deserialize(value) {
      try {
        return deserialize(value);
      } catch {
        return RESET;
      }
    },
  });

  const anAtom: WritableAtom<Value, [SetStateAction<Value> | typeof RESET], void> = atom(
    (get, options) => {
      const hash = get(hashAtom);
      return hash === RESET ? getDefault(get, options) : hash;
    },
    (get, set, update) => {
      if (update === RESET || update == null) {
        set(hashAtom, RESET);
      } else if (isUpdateFunction(update)) {
        const prevValue = get(anAtom);
        const nextValue = update(prevValue);
        set(hashAtom, nextValue);
      } else {
        set(hashAtom, update);
      }
    },
  );

  return anAtom;
}

function isUpdateFunction<Value>(
  value: SetStateAction<Value>,
): value is (prevValue: Value) => Value {
  return typeof value === "function";
}
