import type { RailProvider } from "./types";

export interface FallbackResult<T> {
  result: T;
  providerName?: string;
  errors: string[];
}

export class AllProvidersFailed extends Error {
  public readonly errors: string[];

  constructor(errors: string[]) {
    super(errors.join("; "));
    this.name = "AllProvidersFailed";
    this.errors = errors;
  }
}

type SearchArgs = [string] | [string, { limit?: number }];
type DepartureArgs = [string, { destinationCrs?: string; limit?: number; when?: Date }];

type MethodArgs = SearchArgs | DepartureArgs;

type MethodName = "searchStation" | "getDepartures";

export async function callWithFallback<T>(
  providers: RailProvider[],
  method: MethodName,
  args: MethodArgs,
  { retryOnEmpty = false }: { retryOnEmpty?: boolean } = {}
): Promise<FallbackResult<T>> {
  const errors: string[] = [];
  let lastResult: T | undefined;
  let lastProvider: string | undefined;

  for (const provider of providers) {
    try {
      if (method === "searchStation") {
        const [query, options] = args as SearchArgs;
        const limit = options?.limit;
        console.info(`[fallback] ${provider.name}.${method} query="${query}" limit=${limit ?? "default"}`);
        const result = (await provider.searchStation(query, limit)) as T;
        if (Array.isArray(result)) {
          if (result.length || !retryOnEmpty) {
            console.info(`[fallback] ${provider.name} succeeded (${result.length} items)`);
            return { result, providerName: provider.name, errors };
          }
        } else if (!retryOnEmpty) {
          console.info(`[fallback] ${provider.name} succeeded`);
          return { result, providerName: provider.name, errors };
        }
        console.info(`[fallback] ${provider.name} returned empty result`);
        lastResult = result;
        lastProvider = provider.name;
      } else {
        const [origin, options] = args as DepartureArgs;
        console.info(
          `[fallback] ${provider.name}.${method} origin=${origin} destination=${options.destinationCrs ?? "-"} limit=${options.limit ?? "default"}`
        );
        const result = (await provider.getDepartures(origin, options)) as T;
        if (Array.isArray(result)) {
          if (result.length || !retryOnEmpty) {
            console.info(`[fallback] ${provider.name} succeeded (${result.length} items)`);
            return { result, providerName: provider.name, errors };
          }
        } else if (!retryOnEmpty) {
          console.info(`[fallback] ${provider.name} succeeded`);
          return { result, providerName: provider.name, errors };
        }
        console.info(`[fallback] ${provider.name} returned empty result`);
        lastResult = result;
        lastProvider = provider.name;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`[fallback] ${provider.name} error: ${message}`);
      errors.push(`${provider.name}: ${message}`);
    }
  }

  if (lastResult !== undefined) {
    console.info(`[fallback] returning last non-empty result from ${lastProvider ?? "unknown"}`);
    return { result: lastResult, providerName: lastProvider, errors };
  }

  if (errors.length) {
    console.error("[fallback] all providers failed", errors);
    throw new AllProvidersFailed(errors);
  }

  console.info("[fallback] all providers returned empty result set");
  return { result: [] as T, providerName: undefined, errors };
}
