import { formatDepartures } from "./formatter";
import type { BotSettings } from "./config";
import type { RailProvider } from "./providers/types";
import { callWithFallback, AllProvidersFailed } from "./providers/fallback";
import type { StationSummary, Departure } from "./models";
import type { TelegramBot, TelegramMessage, TelegramUpdate } from "./telegram";

interface CommandContext {
  settings: BotSettings;
  providers: RailProvider[];
  bot: TelegramBot;
}

interface JourneyRequest {
  originQuery: string;
  destinationQuery: string;
  when?: Date;
}

export async function handleUpdate(update: TelegramUpdate, context: CommandContext): Promise<void> {
  const message = update.message;
  if (!message || !message.text) {
    return;
  }

  const { command, argsText } = extractCommand(message);
  switch (command) {
    case "/start":
      await context.bot.sendMessage(message.chat.id, buildStartMessage());
      break;
    case "/help":
      await context.bot.sendMessage(message.chat.id, buildHelpMessage());
      break;
    case "/stations":
      await handleStations(argsText, message, context);
      break;
    case "/journey":
      await handleJourney(argsText, message, context);
      break;
    default:
      await context.bot.sendMessage(
        message.chat.id,
        "Unknown command. Try /help for usage instructions."
      );
  }
}

function extractCommand(message: TelegramMessage): { command: string; argsText: string } {
  const text = message.text ?? "";
  const trimmed = text.trim();
  if (!trimmed.startsWith("/")) {
    return { command: "", argsText: trimmed };
  }
  const [firstToken, ...rest] = trimmed.split(/\s+/);
  const command = (firstToken ?? "").split("@")[0].toLowerCase();
  const argsText = rest.join(" ");
  return { command, argsText };
}

function buildStartMessage(): string {
  return (
    "👋 Hi! Send /journey followed by origin and destination, e.g.\n" +
    "/journey London Waterloo to Winchester at 17:30\n\n" +
    "Need a station code? Try /stations <search term>."
  );
}

function buildHelpMessage(): string {
  return (
    "Usage:\n" +
    "  /journey <origin> to <destination> [at HH:MM]\n" +
    "  /stations <search term>\n\n" +
    "Examples:\n" +
    "  /journey Manchester Piccadilly to London Euston\n" +
    "  /journey Leeds to York at 09:15\n" +
    "  /stations Paddington"
  );
}

async function handleStations(argsText: string, message: TelegramMessage, context: CommandContext): Promise<void> {
  const query = argsText.trim();
  if (!query) {
    await context.bot.sendMessage(
      message.chat.id,
      "Please supply a station name, e.g. /stations York"
    );
    return;
  }

  try {
    const { result, providerName, errors } = await callWithFallback<StationSummary[]>(
      context.providers,
      "searchStation",
      [query, { limit: 5 }],
      { retryOnEmpty: true }
    );

    if (!result.length) {
      await context.bot.sendMessage(message.chat.id, "No stations found for that search term.");
      return;
    }

    const lines = result.map((station) => `${station.name} — ${station.stationCode}`);
    const header = providerName ? `Station matches (via ${providerName})` : "Station matches";
    const diagnostics = errors.map((err) => `Fallback note: ${err}`).join("\n");
    const body = diagnostics
      ? `${header}\n${diagnostics}\n${lines.join("\n")}`
      : `${header}:\n${lines.join("\n")}`;

    await context.bot.sendMessage(message.chat.id, body);
  } catch (error) {
    if (error instanceof AllProvidersFailed) {
      await context.bot.sendMessage(
        message.chat.id,
        "All data providers failed while searching for stations:\n" + error.errors.join("\n")
      );
    } else {
      await context.bot.sendMessage(message.chat.id, "Unexpected error while searching for stations.");
    }
  }
}

async function handleJourney(argsText: string, message: TelegramMessage, context: CommandContext): Promise<void> {
  const query = argsText.trim();
  if (!query) {
    await context.bot.sendMessage(
      message.chat.id,
      "Please provide origin and destination, e.g. /journey Bristol Temple Meads to Bath Spa"
    );
    return;
  }

  let request: JourneyRequest;
  try {
    request = parseJourneyQuery(query);
  } catch (error) {
    await context.bot.sendMessage(message.chat.id, error instanceof Error ? error.message : String(error));
    return;
  }

  try {
    const originResult = await callWithFallback<StationSummary[]>(
      context.providers,
      "searchStation",
      [request.originQuery, { limit: 3 }],
      { retryOnEmpty: true }
    );
    const destinationResult = await callWithFallback<StationSummary[]>(
      context.providers,
      "searchStation",
      [request.destinationQuery, { limit: 3 }],
      { retryOnEmpty: true }
    );

    const originCandidates = originResult.result;
    const destinationCandidates = destinationResult.result;

    if (!originCandidates.length) {
      await context.bot.sendMessage(message.chat.id, "Couldn't find a station matching the origin.");
      return;
    }
    if (!destinationCandidates.length) {
      await context.bot.sendMessage(message.chat.id, "Couldn't find a station matching the destination.");
      return;
    }

    const origin = originCandidates[0];
    const destination = destinationCandidates[0];

    const departureResult = await callWithFallback<Departure[]>(
      context.providers,
      "getDepartures",
      [origin.stationCode, {
        destinationCrs: destination.stationCode,
        limit: context.settings.defaultResultLimit,
        when: request.when
      }],
      { retryOnEmpty: true }
    );

    const originName = tidyStationName(origin.name);
    const destinationName = tidyStationName(destination.name);

    const messageBody = formatDepartures(
      originName,
      destinationName,
      departureResult.result,
      request.when
    );

    const suffix = formatAlternatives(originCandidates, destinationCandidates);
    const providerNote = buildProviderNote(
      departureResult.providerName ?? originResult.providerName ?? destinationResult.providerName
    );
    const diagnostics = [...originResult.errors, ...destinationResult.errors, ...departureResult.errors]
      .map((err) => `Fallback note: ${err}`)
      .join("\n");

    const finalComponents = [messageBody];
    if (suffix) {
      finalComponents.push(suffix);
    }
    if (providerNote) {
      finalComponents.push(providerNote);
    }
    if (diagnostics) {
      finalComponents.push(`\n${diagnostics}`);
    }

    await context.bot.sendMessage(message.chat.id, finalComponents.join(""));
  } catch (error) {
    if (error instanceof AllProvidersFailed) {
      await context.bot.sendMessage(
        message.chat.id,
        "All data providers failed while fetching journey information:\n" + error.errors.join("\n")
      );
    } else {
      await context.bot.sendMessage(message.chat.id, "Unexpected error while fetching journey information.");
    }
  }
}

function parseJourneyQuery(text: string): JourneyRequest {
  const timeMatch = text.match(/(?:\bat\s+)?(\d{1,2}:\d{2})$/i);
  let when: Date | undefined;
  let queryText = text;

  if (timeMatch && typeof timeMatch.index === "number") {
    const [hoursStr, minutesStr] = timeMatch[1].split(":");
    const hours = Number(hoursStr);
    const minutes = Number(minutesStr);
    if (Number.isNaN(hours) || Number.isNaN(minutes) || hours > 23 || minutes > 59) {
      throw new Error("Couldn't parse journey time. Use HH:MM format.");
    }
    const now = new Date();
    when = new Date(now);
    when.setHours(hours, minutes, 0, 0);
    queryText = text.slice(0, timeMatch.index).trim();
  }

  const parts = queryText.split(/\s+(?:to|->)\s+/i);
  if (parts.length !== 2) {
    throw new Error("Couldn't parse journey. Use '/journey origin to destination [at HH:MM]'.");
  }

  const originQuery = stripFromKeyword(parts[0]);
  const destinationQuery = stripFromKeyword(parts[1]);

  if (!originQuery || !destinationQuery) {
    throw new Error("Origin and destination are both required.");
  }

  return { originQuery, destinationQuery, when };
}

function stripFromKeyword(value: string): string {
  return value.replace(/^(?:from|to)\s+/i, "").trim();
}

function tidyStationName(name: string): string {
  return name.replace(/\bRail (Station|Stn)\b/gi, "").trim();
}

function formatAlternatives(
  originCandidates: StationSummary[],
  destinationCandidates: StationSummary[]
): string {
  const originSuffix = formatStationCandidates("Origin suggestions", originCandidates);
  const destinationSuffix = formatStationCandidates("Destination suggestions", destinationCandidates);
  const additions = [originSuffix, destinationSuffix].filter(Boolean).join("");
  return additions ? `\n\n${additions}` : "";
}

function formatStationCandidates(label: string, candidates: StationSummary[]): string {
  if (candidates.length <= 1) {
    return "";
  }
  const formatted = candidates
    .slice(1, 3)
    .map((station) => `- ${station.name} — ${station.stationCode}`)
    .join("\n");
  return formatted ? `${label}:\n${formatted}\n` : "";
}

function buildProviderNote(providerName?: string): string {
  return providerName ? `\n\nData source: ${providerName}` : "";
}
