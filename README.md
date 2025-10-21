# Train Schedule Telegram Bot

A Telegram bot that surfaces up-to-date UK rail departure information between two stations using the TransportAPI public service.

## Features
- `/journey <origin> to <destination> [at HH:MM]` lists upcoming direct services calling at the destination.
- `/stations <query>` searches TransportAPI for station codes when you only know part of the name.
- Friendly formatting that highlights operator, platform, timing, and notable calling points.

## Prerequisites
- Python 3.11 or newer.
- Telegram Bot API token via [@BotFather](https://core.telegram.org/bots#6-botfather).
- TransportAPI credentials (app id + app key) from [transportapi.com](https://www.transportapi.com/).

## Setup
### Using uv (recommended)
1. Ensure [uv](https://github.com/astral-sh/uv) is installed locally.
2. Sync the environment and dependencies:
   ```bash
   uv sync
   ```
   This creates `.venv/` and installs the dependencies declared in `pyproject.toml`.
3. Provide credentials via environment variables or a `.env` file in the project root:
   ```env
   TELEGRAM_BOT_TOKEN=123456:abc...
   TRANSPORT_API_APP_ID=your-app-id
   TRANSPORT_API_APP_KEY=your-app-key
   # Optional: override defaults
   # DEFAULT_RESULT_LIMIT=5
   # TRANSPORT_API_BASE_URL=https://transportapi.com/v3
   ```

### Using pip (alternative)
If you prefer vanilla `pip`:
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies from the same lock step as `pyproject.toml`:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Bot
With the virtualenv active and environment variables set, start the bot:
```bash
uv run python -m train_bot
```
or, if you have activated the virtual environment manually:
```bash
python -m train_bot
```

## Container & Kubernetes Deployment

### Build the Container Image
1. Authenticate to your registry (e.g. `ghcr.io/niuguy/train-bot`).
2. Build and push a multi-arch image (replace the tag if you use a different registry):
   ```bash
   docker buildx build --platform linux/amd64,linux/arm64 \
     -t ghcr.io/niuguy/train-bot:latest \
     --push .
   ```

### k3s / ArgoCD Manifests
- `k8s/train-bot/deployment.yaml` defines a single replica worker that pulls the `ghcr.io/niuguy/train-bot:latest` image and injects secrets via `train-bot-secrets`.
- `k8s/train-bot/secret-example.yaml` shows the expected keys—create the real secret out-of-band:
  ```bash
  kubectl create secret generic train-bot-secrets \
    --from-literal=TELEGRAM_BOT_TOKEN=... \
    --from-literal=TRANSPORT_API_APP_ID=... \
    --from-literal=TRANSPORT_API_APP_KEY=...
  ```
- `k8s/train-bot/kustomization.yaml` lets ArgoCD sync the deployment directory directly.

Point an ArgoCD Application at `k8s/train-bot` and set the image tag via Kustomize patch or environment-specific overlays if needed.

### GitHub Actions Build (GHCR)
This repository includes `.github/workflows/publish.yml`, which builds a multi-arch image (`linux/amd64`, `linux/arm64`) and pushes it to `ghcr.io/niuguy/train-bot:latest` on each push to `main` (and on tagged releases). Make sure the repository has GitHub Packages enabled and that the workflow user has permission to push to GHCR (default `GITHUB_TOKEN` works for public repositories).
The bot will run in polling mode and respond to incoming Telegram messages.

## Command Reference
- `/start` – get a quick primer.
- `/journey London Waterloo to Winchester` – show the next services calling at Winchester.
- `/journey Leeds to York at 09:15` – request departures after a specific time.
- `/stations Paddington` – list matching stations with CRS codes when you are unsure of the spelling.

## Notes & Limitations
- TransportAPI free tier requests are rate limited; consider caching or back-off if you expect higher usage.
- Times are treated as local UK times without daylight-saving adjustments.
- The bot filters by destination using the `calling_at` parameter; it does not currently offer interchange planning or multi-leg journey results.

## Next Steps
- Add keyboards or buttons to let users pick from multiple station matches interactively.
- Extend parsing to support dates (`at 09:15 tomorrow`, `on 2024-06-15`).
- Hook into a persistence layer if you need to remember user preferences (home station, favourite journeys, etc.).
