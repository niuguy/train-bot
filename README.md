# Train Schedule Telegram Bot

A TypeScript Telegram bot that surfaces up-to-date UK rail departure information between two stations. The bot now runs as a Cloudflare Worker, receives updates through a Telegram webhook, and queries RealTimeTrains with an optional TransportAPI fallback when the primary provider is unavailable.

## Features
- `/journey <origin> to <destination> [at HH:MM]` lists upcoming direct services including status, platform, and calling points.
- `/stations <query>` searches configured providers for CRS codes when you only know part of the station name.
- Automatic fallback between RealTimeTrains and TransportAPI, with diagnostics in the reply when a provider fails.

## Prerequisites
- Node.js 18 or newer (required by Wrangler and Cloudflare Workers).
- [Yarn](https://yarnpkg.com/) (v1 or Berry) for dependency management.
- A Telegram Bot API token from [@BotFather](https://core.telegram.org/bots#6-botfather).
- RealTimeTrains API credentials (username/password) from [realtimetrains.co.uk](https://www.realtimetrains.co.uk/).
- (Optional) TransportAPI credentials (app id + app key) from [transportapi.com](https://www.transportapi.com/).
- A Cloudflare account with permissions to deploy Workers.

## Project Structure
```
worker/
  package.json       – scripts and dev dependencies (Wrangler, TypeScript)
  tsconfig.json      – strict type checking for Worker source
  wrangler.toml      – Worker definition and default vars
  src/               – Worker TypeScript sources
```

## Configuration
The Worker reads its configuration from Cloudflare environment bindings:

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram HTTP API token. |
| `RTT_USERNAME` / `RTT_PASSWORD` | ✅ (one provider required) | RealTimeTrains credentials. |
| `TRANSPORT_API_APP_ID` / `TRANSPORT_API_APP_KEY` | Optional | TransportAPI fallback credentials. |
| `DEFAULT_STATION_FILTER_LIMIT` | Optional | Max departures returned for `/journey` (default `5`). |
| `RTT_BASE_URL` / `TRANSPORT_API_BASE_URL` | Optional | Override provider API base URLs (defaults match public APIs). |

Configure the secrets with Wrangler:
```bash
cd worker
yarn wrangler secret put TELEGRAM_BOT_TOKEN
yarn wrangler secret put RTT_USERNAME
yarn wrangler secret put RTT_PASSWORD
# Optional TransportAPI fallback
yarn wrangler secret put TRANSPORT_API_APP_ID
yarn wrangler secret put TRANSPORT_API_APP_KEY
```
Set plain vars (non-secret) in `wrangler.toml` or with `wrangler kv:namespace` bindings as needed. The provided `wrangler.toml` already sets `DEFAULT_STATION_FILTER_LIMIT=5`.

## Local Development
```bash
cd worker
yarn install
bash dev.sh          # local mode (http://localhost:8787)
bash dev.sh --remote # run on Cloudflare edge, get https:// URL
```
`dev.sh` loads credentials from the current environment or from `worker/.dev.vars` (simple `KEY=value` lines), then forwards them to `wrangler dev`. Use the `--remote` flag when you need an HTTPS endpoint for Telegram’s webhook; Cloudflare will expose a workers.dev URL automatically. Local mode is handy for manual testing (`curl` against `http://localhost:8787`).

Example `worker/.dev.vars` file:
```env
TELEGRAM_BOT_TOKEN=8263616062:AAHgCOo194cDFzCGPQcbFxYL2ewYzsGs2i8
RTT_USERNAME=rttapi_niuguy
RTT_PASSWORD=a0d877bf69978802645c616e11c0b3c6f80628f3
# TRANSPORT_API_APP_ID=optional
# TRANSPORT_API_APP_KEY=optional
```

Run type checks:
```bash
yarn check
```

Run the live RTT integration test (requires `RTT_USERNAME` and `RTT_PASSWORD` in your environment):
```bash
yarn test:live
```
Override the test flow with `RTT_TEST_ORIGIN=<CRS>` / `RTT_TEST_DESTINATION=<CRS>` if you want to probe a specific station pair.

## Deployment
```bash
cd worker
yarn install --immutable
yarn deploy
```
`yarn deploy` invokes `wrangler deploy`, publishes the Worker to Cloudflare, and prints the public URL (e.g. `https://train-bot-worker.your-account.workers.dev`).

After deployment, point Telegram at the Worker webhook endpoint:
```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://train-bot-worker.your-account.workers.dev"}'
```
Telegram will now POST updates to the Worker, which replies to chats using the same command semantics as before. A simple GET request to the Worker URL returns `train-bot worker ready`, which Telegram ignores but is useful for health checks.

## Command Reference
- `/start` – greeting and usage primer.
- `/help` – full command usage reference.
- `/journey London Waterloo to Winchester` – next services calling at Winchester.
- `/journey Leeds to York at 09:15` – departures after a specific time.
- `/stations Paddington` – list matching stations with CRS codes.

## Notes & Limitations
- RealTimeTrains and TransportAPI enforce rate limits; the Worker does not implement caching or circuit-breaking beyond the provider fallback.
- Time parsing supports `HH:MM` in local UK time only; relative dates (`tomorrow`) remain future work.
- Telegram webhooks expect a timely `200 OK`. Any internal error results in a `500` so Telegram can retry.

## Next Steps
1. Add persistent storage (Workers KV, D1, or R2) for user preferences.
2. Support inline keyboards for selecting among multiple station matches.
3. Extend parsing to handle explicit travel dates or relative terms.
