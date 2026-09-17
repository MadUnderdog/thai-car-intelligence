import type { SourceConfig } from "./types";

/**
 * Small process-local registry. Applications should populate it from configuration;
 * this module intentionally ships with no permanent brand/domain list.
 */
export class SourceRegistry {
  private readonly sources = new Map<string, SourceConfig>();

  constructor(initial: readonly SourceConfig[] = []) {
    for (const source of initial) this.register(source);
  }

  register(source: SourceConfig): this {
    if (!source.id.trim()) throw new Error("Source id must not be empty");
    this.sources.set(source.id, { ...source });
    return this;
  }

  get(id: string): SourceConfig | undefined {
    const source = this.sources.get(id);
    return source ? { ...source } : undefined;
  }

  has(id: string): boolean {
    return this.sources.has(id);
  }

  remove(id: string): boolean {
    return this.sources.delete(id);
  }

  list(): SourceConfig[] {
    return [...this.sources.values()].map((source) => ({ ...source }));
  }
}

export function createSourceRegistry(initial: readonly SourceConfig[] = []): SourceRegistry {
  return new SourceRegistry(initial);
}
