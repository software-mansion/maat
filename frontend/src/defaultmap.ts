export class DefaultMap<K, V> extends Map<K, V> {
  private readonly defaultFactory: () => V;

  constructor(defaultFactory: () => V) {
    super();
    this.defaultFactory = defaultFactory;
  }

  get(key: K): V {
    if (this.has(key)) {
      return super.get(key)!;
    } else {
      const defaultValue = this.defaultFactory();
      this.set(key, defaultValue);
      return defaultValue;
    }
  }

  has(key: K): boolean {
    return super.has(key);
  }
}
