export interface CallingPoint {
  stationName: string;
  stationCode: string;
  aimedArrivalTime?: string;
  expectedArrivalTime?: string;
}

export interface Departure {
  serviceUid: string;
  destinationName: string;
  destinationCode: string;
  platform?: string;
  aimedDepartureTime?: string;
  expectedDepartureTime?: string;
  status: string;
  callingPoints: CallingPoint[];
  operatorName?: string;
}

export interface StationSummary {
  name: string;
  stationCode: string;
}
