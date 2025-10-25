import type { ExecutionContext } from "@cloudflare/workers-types";
import { loadSettings, type BotSettings, type Env } from "./config";
import { RttProvider } from "./providers/rtt";
import { TransportApiProvider } from "./providers/transportApi";
import type { RailProvider } from "./providers/types";
import { TelegramBot, type TelegramUpdate } from "./telegram";
import { handleUpdate } from "./commands";

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    if (request.method === "GET") {
      return new Response("train-bot worker ready", { status: 200 });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let update: TelegramUpdate;
    try {
      update = (await request.json()) as TelegramUpdate;
    } catch (error) {
      return new Response("Invalid JSON payload", { status: 400 });
    }

    let settings: BotSettings;
    let providers: RailProvider[];
    let bot: TelegramBot;
    try {
      settings = loadSettings(env);
      providers = createProviders(settings);
      bot = new TelegramBot(settings.telegramToken);
    } catch (error) {
      console.error("Configuration error", error);
      return new Response("Server misconfigured", { status: 500 });
    }

    try {
      await handleUpdate(update, { settings, providers, bot });
    } catch (error) {
      console.error("Failed to handle update", error);
      return new Response("Failed to process update", { status: 500 });
    }

    return new Response("ok", { status: 200 });
  }
};

function createProviders(settings: BotSettings): RailProvider[] {
  const providers: RailProvider[] = [];
  if (settings.rttSettings) {
    providers.push(new RttProvider(settings.rttSettings));
  }
  if (settings.transportSettings) {
    providers.push(new TransportApiProvider(settings.transportSettings));
  }
  return providers;
}
