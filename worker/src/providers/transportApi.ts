import type { Departure, StationSummary, CallingPoint } from "../models";
import type { RailProvider } from "./types";
import { ProviderError } from "./types";

export interface TransportApiOptions {
  appId: string;
  appKey: string;
  baseUrl: string;
}

export class TransportApiProvider implements RailProvider {
  readonly name = "TransportAPI";

  constructor(private readonly options: TransportApiOptions) {}

  async searchStation(query: string, limit = 5): Promise<StationSummary[]> {
    const url = new URL("/uk/places.json", this.options.baseUrl);
    url.searchParams.set("app_id", this.options.appId);
    url.searchParams.set("app_key", this.options.appKey);
    url.searchParams.set("query", query);
    url.searchParams.set("type", "train_station");
    url.searchParams.set("limit", String(limit));

    const payload = await this.fetchJson<{ member?: Array<Record<string, unknown>> }>(url);
    const members = payload.member ?? [];
    const results: StationSummary[] = [];
    for (const item of members) {
      const code = item.station_code;
      const name = item.name;
      if (typeof code !== "string" || typeof name !== "string") {
        continue;
      }
      results.push({ name, stationCode: code });
      if (results.length >= limit) {
        break;
      }
    }
    return results;
  }

  async getDepartures(
    originCrs: string,
    {
      destinationCrs,
      limit = 5,
      when
    }: { destinationCrs?: string; limit?: number; when?: Date }
  ): Promise<Departure[]> {
    const url = new URL(`/uk/train/station/${originCrs}/live.json`, this.options.baseUrl);
    url.searchParams.set("app_id", this.options.appId);
    url.searchParams.set("app_key", this.options.appKey);
    url.searchParams.set("limit", String(limit));
    url.searchParams.set("station_detail", "calling_at");

    if (destinationCrs) {
      url.searchParams.set("calling_at", destinationCrs);
    }
    if (when) {
      url.searchParams.set("date", formatDate(when));
      url.searchParams.set("time", formatTime(when));
    }

    const payload = await this.fetchJson<any>(url);
    const departures = payload.departures?.all ?? [];

    return departures.slice(0, limit).map((item: any) => parseDeparture(item));
  }

  private async fetchJson<T>(url: URL): Promise<T> {
    const response = await fetch(url.toString(), {
      headers: { Accept: "application/json" }
    });

    const text = await response.text();
    console.info(`[transportapi] GET ${url.pathname} -> ${response.status}`);
    console.info(`[transportapi] response body: ${text.slice(0, 500)}`);
    if (response.status === 404) {
      console.info("[transportapi] No data returned (404)");
      return {} as T;
    }
    if (!response.ok) {
      throw new ProviderError(
        `TransportAPI error ${response.status}: ${text.slice(0, 200) || "<empty>"}`
      );
    }

    try {
      return JSON.parse(text) as T;
    } catch (error) {
      console.error("[transportapi] Failed to parse JSON", text.slice(0, 200));
      throw new ProviderError(`TransportAPI returned invalid JSON: ${text.slice(0, 200)}`);
    }
  }
}

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatTime(date: Date): string {
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}

function parseDeparture(data: any): Departure {
  const stationDetails = data.station_detail ?? {};
  const callingPointsData = stationDetails.calling_at ?? data.calling_at ?? [];
  const callingPoints: CallingPoint[] = Array.isArray(callingPointsData)
    ? callingPointsData.map((point: any) => ({
        stationName: point.station_name ?? "",
        stationCode: point.station_code ?? "",
        aimedArrivalTime: point.aimed_arrival_time ?? point.aimed_pass_time ?? undefined,
        expectedArrivalTime: point.expected_arrival_time ?? undefined
      }))
    : [];

  const destinationName = extractDestinationName(data);
  const destinationCode = findDestinationCode(destinationName, callingPoints);

  return {
    serviceUid: data.train_uid ?? "",
    destinationName,
    destinationCode,
    platform: data.platform ?? undefined,
    aimedDepartureTime: data.aimed_departure_time ?? undefined,
    expectedDepartureTime: data.expected_departure_time ?? data.aimed_departure_time ?? undefined,
    status: data.status ?? "",
    callingPoints,
    operatorName: data.operator_name ?? data.operator ?? undefined
  };
}

function extractDestinationName(data: any): string {
  const destination = data.destination_name;
  if (Array.isArray(destination) && destination.length) {
    return destination[0] ?? "Unknown";
  }
  if (typeof destination === "string" && destination.length) {
    return destination;
  }
  return "Unknown";
}

function findDestinationCode(name: string, callingPoints: CallingPoint[]): string {
  for (const point of callingPoints) {
    if (point.stationName === name) {
      return point.stationCode;
    }
  }
  return "";
}
