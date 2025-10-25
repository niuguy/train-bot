import type { Departure, StationSummary } from "../models";

export interface RailProvider {
  name: string;
  searchStation(query: string, limit?: number): Promise<StationSummary[]>;
  getDepartures(
    originCrs: string,
    options: {
      destinationCrs?: string;
      limit?: number;
      when?: Date;
    }
  ): Promise<Departure[]>;
}

export class ProviderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProviderError";
  }
}
