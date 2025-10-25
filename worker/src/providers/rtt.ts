import type { CallingPoint, Departure, StationSummary } from "../models";
import type { RailProvider } from "./types";
import { ProviderError } from "./types";

export interface RttOptions {
  username: string;
  password: string;
  baseUrl: string;
}

interface RttServicePayload {
  serviceUid?: string;
  runDate?: string;
  atocName?: string;
  atocCode?: string;
  locationDetail?: Record<string, unknown>;
}

export class RttProvider implements RailProvider {
  readonly name = "RealTimeTrains";

  constructor(private readonly options: RttOptions) {}

  async searchStation(query: string, limit = 5): Promise<StationSummary[]> {
    const cleaned = query.trim();
    if (!cleaned) {
      return [];
    }

    const variants = this.buildSearchVariants(cleaned);
    let fallbackStation: StationSummary | undefined;

    for (const variant of variants) {
      const path = `/api/v1/json/search/${encodeURIComponent(variant)}`;
      console.info(`[rtt] search variant="${variant}"`);
      const payload = await this.fetchJson<{ locations?: Array<Record<string, string>>; location?: Record<string, unknown> }>(path);

      const matches = this.extractStations(payload.locations ?? [], limit);
      if (matches.length) {
        return matches;
      }

      if (!fallbackStation) {
        fallbackStation = this.extractFallbackStation(payload.location);
      }
    }

    return fallbackStation ? [fallbackStation] : [];
  }

  private buildSearchVariants(query: string): string[] {
    const variants = new Set<string>();
    variants.add(query);
    variants.add(query.toLowerCase());
    variants.add(query.toUpperCase());
    variants.add(
      query
        .split(/\s+/)
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(" ")
    );
    return Array.from(variants).filter(Boolean);
  }

  private extractStations(locations: Array<Record<string, string>>, limit: number): StationSummary[] {
    const matches: StationSummary[] = [];
    for (const item of locations) {
      const code = item.crs;
      const name = item.name ?? item.description;
      if (!code || !name) {
        continue;
      }
      matches.push({ name, stationCode: code });
      if (matches.length >= limit) {
        break;
      }
    }
    return matches;
  }

  private extractFallbackStation(location: Record<string, unknown> | undefined): StationSummary | undefined {
    if (!location) {
      return undefined;
    }
    const code = typeof location?.crs === "string" ? location.crs : undefined;
    const nameCandidate =
      typeof location?.name === "string"
        ? location.name
        : typeof location?.description === "string"
          ? (location.description as string)
          : undefined;
    if (code && nameCandidate) {
      return { name: nameCandidate, stationCode: code };
    }
    return undefined;
  }

  async getDepartures(
    originCrs: string,
    { destinationCrs, limit = 5, when }: { destinationCrs?: string; limit?: number; when?: Date }
  ): Promise<Departure[]> {
    const origin = originCrs.toUpperCase();
    const destination = destinationCrs?.toUpperCase() ?? "";
    const path = destination
      ? `/api/v1/json/search/${origin}/to/${destination}`
      : `/api/v1/json/dep/${origin}`;

    const payload = await this.fetchJson<{ services?: RttServicePayload[] }>(path);
    const services = payload.services ?? [];
    const departures: Departure[] = [];

    for (const service of services) {
      const detail = (service.locationDetail ?? {}) as Record<string, any>;
      const aimed: string | undefined = detail.gbttBookedDeparture;
      const expected: string | undefined = detail.realtimeDeparture ?? detail.gbttBookedDeparture;
      const runDate = service.runDate;

      if (when && runDate && aimed) {
        const runDateTime = parseRttDate(runDate, aimed);
        if (runDateTime && runDateTime < when) {
          continue;
        }
      }

      const [destinationName, destinationCode] = selectDestination(detail);
      const callingPoints = parseCallingPoints(detail);
      const status = deriveStatus(detail);

      departures.push({
        serviceUid: service.serviceUid ?? "",
        destinationName,
        destinationCode,
        platform: detail.platform,
        aimedDepartureTime: aimed,
        expectedDepartureTime: expected,
        status,
        callingPoints,
        operatorName: service.atocName ?? service.atocCode
      });
    }

    return departures.slice(0, limit);
  }

  private async fetchJson<T>(path: string): Promise<T> {
    const url = new URL(path, this.options.baseUrl);
    const auth = btoa(`${this.options.username}:${this.options.password}`);
    const response = await fetch(url.toString(), {
      headers: {
        Accept: "application/json",
        Authorization: `Basic ${auth}`
      }
    });

    const text = await response.text();

    console.info(`[rtt] GET ${url.pathname} -> ${response.status}`);
    console.info(`[rtt] response body: ${text.slice(0, 500)}`);

    if (response.status === 404) {
      console.info("[rtt] No services returned (404)");
      return {} as T;
    }

    if (!response.ok) {
      throw new ProviderError(
        `RealTimeTrains error ${response.status}: ${text.slice(0, 200) || "<empty>"}`
      );
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      console.error("[rtt] Failed to parse JSON", text.slice(0, 200));
      throw new ProviderError(`RealTimeTrains returned invalid JSON: ${text.slice(0, 200)}`);
    }
  }
}

function parseRttDate(runDate: string, time: string): Date | undefined {
  const combined = `${runDate}T${time}:00`;
  const parsed = new Date(combined);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function selectDestination(detail: Record<string, any>): [string, string] {
  const destinations = detail.destination ?? [];
  if (Array.isArray(destinations) && destinations.length) {
    const dest = destinations[0] ?? {};
    return [dest.description ?? "Unknown", dest.crs ?? ""];
  }
  return ["Unknown", ""];
}

function parseCallingPoints(detail: Record<string, any>): CallingPoint[] {
  const raw = detail.callPoints ?? [];
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map((point: any) => {
    const location = point.location ?? {};
    return {
      stationName: location.description ?? "",
      stationCode: location.crs ?? "",
      aimedArrivalTime: point.gbttBookedArrival ?? point.gbttBookedPass ?? undefined,
      expectedArrivalTime: point.realtimeArrival ?? point.realtimePass ?? undefined
    };
  });
}

function deriveStatus(detail: Record<string, any>): string {
  if (detail.isCancelled) {
    return "CANCELLED";
  }
  if (detail.displayAs) {
    return String(detail.displayAs).toUpperCase();
  }
  if (detail.realtimeDepartureActual) {
    return `DEPARTED ${detail.realtimeDepartureActual}`;
  }
  if (detail.realtimeDeparture) {
    return `EXPECTED ${detail.realtimeDeparture}`;
  }
  return "UNKNOWN";
}
