# Qwen Code Config Generator

Generates `~/.qwen/settings.json` from a local `.env` and live provider catalogs.
Credential values are never copied into the generated configuration.

## Inspect detected providers

```bash
python3 scripts/zai-config-gen.py --env-file .env env-status
```

## Generate strict-free and local configuration

```bash
python3 scripts/zai-config-gen.py --env-file .env generate
```

## Generate all account-accessible models

```bash
python3 scripts/zai-config-gen.py --env-file .env generate --include-accessible
```

## Limit providers

```bash
python3 scripts/zai-config-gen.py --env-file .env generate \
  --include-accessible \
  --providers openrouter,nvidia-nim,groq,ollama,litellm
```

## Validate output

```bash
python3 scripts/zai-config-gen.py validate
```

## Rotate active model

```bash
python3 scripts/zai-config-gen.py rotate
```

## Show status

```bash
python3 scripts/zai-config-gen.py status
```

The legacy `refresh` command remains available as an alias of `generate`.
