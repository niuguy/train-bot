export interface Env {
  TELEGRAM_BOT_TOKEN: string;
  DEFAULT_STATION_FILTER_LIMIT?: string;
  RTT_USERNAME?: string;
  RTT_PASSWORD?: string;
  RTT_BASE_URL?: string;
  TRANSPORT_API_APP_ID?: string;
  TRANSPORT_API_APP_KEY?: string;
  TRANSPORT_API_BASE_URL?: string;
}

export interface RttSettings {
  username: string;
  password: string;
  baseUrl: string;
}

export interface TransportApiSettings {
  appId: string;
  appKey: string;
  baseUrl: string;
}

export interface BotSettings {
  telegramToken: string;
  rttSettings?: RttSettings;
  transportSettings?: TransportApiSettings;
  defaultResultLimit: number;
}

export function loadSettings(env: Env): BotSettings {
  const telegramToken = env.TELEGRAM_BOT_TOKEN;
  if (!telegramToken) {
    throw new Error("Missing TELEGRAM_BOT_TOKEN binding");
  }

  const defaultLimit = parseInt(env.DEFAULT_STATION_FILTER_LIMIT ?? "5", 10);

  const rttUsername = env.RTT_USERNAME;
  const rttPassword = env.RTT_PASSWORD;
  const rttBaseUrl = env.RTT_BASE_URL ?? "https://api.rtt.io";

  const transportAppId = env.TRANSPORT_API_APP_ID;
  const transportAppKey = env.TRANSPORT_API_APP_KEY;
  const transportBaseUrl = env.TRANSPORT_API_BASE_URL ?? "https://transportapi.com/v3";

  const rttSettings = rttUsername && rttPassword ? { username: rttUsername, password: rttPassword, baseUrl: rttBaseUrl } : undefined;
  const transportSettings = transportAppId && transportAppKey ? { appId: transportAppId, appKey: transportAppKey, baseUrl: transportBaseUrl } : undefined;

  if (!rttSettings && !transportSettings) {
    throw new Error("Configure at least one rail data provider (RTT or TransportAPI)");
  }

  return {
    telegramToken,
    rttSettings,
    transportSettings,
    defaultResultLimit: Number.isFinite(defaultLimit) ? defaultLimit : 5
  };
}
