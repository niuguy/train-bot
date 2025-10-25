import type { Departure } from "./models";

export function formatDepartures(
  originName: string,
  destinationName: string | undefined,
  departures: Departure[],
  requestedTime?: Date
): string {
  if (!departures.length) {
    return `${formatHeader(originName, destinationName, requestedTime)}\nNo matching services found.`;
  }

  const lines: string[] = [formatHeader(originName, destinationName, requestedTime)];
  departures.forEach((service, index) => {
    const destination = destinationName ?? service.destinationName;
    const timing = formatTiming(service);
    const platform = service.platform ? `Platform ${service.platform}` : "Platform TBC";
    const operator = service.operatorName ?? "Unknown operator";
    const callingPoints = formatCallingPoints(service);

    lines.push(
      [
        `${index + 1}. ${originName} ➜ ${destination}`,
        timing,
        platform,
        `Operator: ${operator}`,
        callingPoints
      ].join("\n")
    );
  });

  return lines.join("\n\n");
}

function formatHeader(
  originName: string,
  destinationName: string | undefined,
  requestedTime?: Date
): string {
  const base = destinationName
    ? `Next services from ${originName} to ${destinationName}`
    : `Next services departing ${originName}`;

  if (!requestedTime) {
    return base;
  }

  const time = requestedTime.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
  const date = requestedTime.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short"
  });

  return `${base} after ${time} on ${date}`;
}

function formatTiming(service: Departure): string {
  const expected = service.expectedDepartureTime;
  const aimed = service.aimedDepartureTime;
  const status = service.status || "UNKNOWN";
  const aimedDisplay = aimed ?? "TBC";

  if (expected && aimed && expected !== aimed) {
    return `Due ${aimedDisplay} (est. ${expected}, ${status})`;
  }
  if (expected && !aimed) {
    return `Due ${expected} (${status})`;
  }
  return `Due ${aimedDisplay} (${status})`;
}

function formatCallingPoints(service: Departure): string {
  if (!service.callingPoints.length) {
    return "Calling points data unavailable.";
  }

  const names = service.callingPoints.map((point) => point.stationName);
  const summary = names.length > 6 ? `${names.slice(0, 6).join(", ")}…` : names.join(", ");
  return `Calling at: ${summary}`;
}
