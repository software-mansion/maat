export function DateTime({ value }: { value: string }) {
  return new Date(value).toLocaleString();
}
