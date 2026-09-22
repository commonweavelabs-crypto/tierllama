# If Hermes ever fails to respond after the Tierllama dogfood setup

You will NOT be disconnected: this session runs on `model.default = glm-5.3-flash:cloud`
via `ollama-launch`, and that block was never touched. The Tierllama provider was
ADDED alongside - it only activates when you switch to it.

## To switch Gui's models to the router (when you choose to):
In Hermes: `/model tierllama-auto --provider tierllama-local`
(or pick from the provider list - "Tierllama (local router)").

## To revert instantly:
`/model glm-5.3-flash:cloud --provider ollama-launch`

## Full manual restore (nuclear option):
1. Stop the proxy: `schtasks /End /TN tierllama-proxy` then
   `schtasks /Delete /TN tierllama-proxy /F`
2. Restore the backup config: copy
   `C:\Users\Guilherme\AppData\Local\hermes\config.yaml.j6-backup-20260922`
   over `config.yaml` (the tierllama-local provider is the only diff).
3. Hermes keeps talking to Ollama directly - nothing else changes.

## What the router logs while you chat:
- `tierllama/logs/proxy.jsonl` - one line per message: difficulty, lane, model, latency
- Dashboard: `python cli.py serve` -> http://127.0.0.1:8848 (or the running :8848 server)
