<!--
Copyright 2026 Terrene Foundation
Licensed under the Apache License, Version 2.0
-->

# CARE Platform Environment Configuration

All CARE Platform configuration is supplied through environment variables. The `.env` file at the repository root is loaded automatically by both the Python server and the Docker Compose setup.

---

## How Configuration Is Loaded

1. At startup, `care_platform.config.env.load_env_config()` is called.
2. It searches for a `.env` file starting from the current working directory, walking up to three parent directories.
3. Variables already present in the process environment take precedence over `.env` values.
4. In Docker Compose, `env_file: .env` injects the file into the container environment before the process starts.

---

## Complete Variable Reference

### Database

| Variable            | Required         | Default             | Description                                                                           |
| ------------------- | ---------------- | ------------------- | ------------------------------------------------------------------------------------- |
| `DATABASE_URL`      | Yes (production) | `""`                | PostgreSQL connection URL. Format: `postgresql://user:pass@host:5432/dbname`          |
| `POSTGRES_PASSWORD` | Yes (Docker)     | `care_dev_password` | Password for the PostgreSQL container. Used by Docker Compose to create the database. |
| `REDIS_URL`         | No               | `""`                | Redis connection URL. Format: `redis://host:6379/0`. Not required for core operation. |

In Docker Compose, `DATABASE_URL` is set automatically to point at the `db` service container. You only need to set `POSTGRES_PASSWORD` in your `.env` file.

### CARE Platform API

| Variable                  | Required | Default                                       | Description                                                                   |
| ------------------------- | -------- | --------------------------------------------- | ----------------------------------------------------------------------------- |
| `CARE_API_TOKEN`          | Yes\*    | `""`                                          | Bearer token for API authentication. Required unless `CARE_DEV_MODE=true`.    |
| `CARE_API_HOST`           | No       | `0.0.0.0`                                     | Host the API server binds to. Do not change in containers.                    |
| `CARE_API_PORT`           | No       | `8000`                                        | Port the API server listens on.                                               |
| `CARE_CORS_ORIGINS`       | No       | `http://localhost:3000,http://localhost:3001` | Comma-separated list of allowed CORS origins.                                 |
| `CARE_MAX_WS_SUBSCRIBERS` | No       | `50`                                          | Maximum concurrent WebSocket connections.                                     |
| `CARE_DEV_MODE`           | No       | `false`                                       | When `true`, allows an empty `CARE_API_TOKEN`. Use only in local development. |

\*`CARE_API_TOKEN` is required unless `CARE_DEV_MODE=true`. The server will refuse to start without it in production mode.

### LLM Providers

Configure at least one LLM provider. The platform will use the first available provider.

#### OpenAI

| Variable            | Required | Default | Description                                           |
| ------------------- | -------- | ------- | ----------------------------------------------------- |
| `OPENAI_API_KEY`    | No       | `""`    | OpenAI API key. Starts with `sk-`.                    |
| `OPENAI_PROD_MODEL` | No       | `""`    | Model name for production workloads (e.g., `gpt-4o`). |
| `OPENAI_DEV_MODEL`  | No       | `""`    | Model name for development (e.g., `gpt-4o-mini`).     |

#### Anthropic

| Variable            | Required | Default | Description                               |
| ------------------- | -------- | ------- | ----------------------------------------- |
| `ANTHROPIC_API_KEY` | No       | `""`    | Anthropic API key. Starts with `sk-ant-`. |
| `ANTHROPIC_MODEL`   | No       | `""`    | Model name (e.g., `claude-sonnet-4-6`).   |

#### Google / Gemini

| Variable         | Required | Default | Description                                       |
| ---------------- | -------- | ------- | ------------------------------------------------- |
| `GOOGLE_API_KEY` | No       | `""`    | Google AI API key.                                |
| `GEMINI_API_KEY` | No       | `""`    | Gemini API key (alternative to `GOOGLE_API_KEY`). |

#### Fallback

| Variable            | Required | Default | Description                                               |
| ------------------- | -------- | ------- | --------------------------------------------------------- |
| `DEFAULT_LLM_MODEL` | No       | `""`    | Fallback model name when no specific model is configured. |

### EATP Trust Protocol

| Variable                      | Required | Default              | Description                                                                                     |
| ----------------------------- | -------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `EATP_GENESIS_AUTHORITY`      | No       | `terrene.foundation` | Authority identifier for the EATP genesis record. Identifies who established the root of trust. |
| `EATP_CREDENTIAL_TTL_SECONDS` | No       | `300`                | Lifetime in seconds for EATP credentials (5 minutes by default).                                |

### Application

| Variable    | Required | Default       | Description                                                                          |
| ----------- | -------- | ------------- | ------------------------------------------------------------------------------------ |
| `APP_ENV`   | No       | `development` | Deployment environment. One of `development`, `staging`, `production`.               |
| `DEBUG`     | No       | `false`       | Enable debug mode (verbose logging, reload on code change). Never use in production. |
| `LOG_LEVEL` | No       | `INFO`        | Python logging level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.        |

---

## Example Configurations

### Local Development

Minimal configuration for running locally with Docker Compose.

```env
# .env — local development
CARE_DEV_MODE=true
POSTGRES_PASSWORD=local_dev_only

# Use one LLM provider
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6

APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
```

No `CARE_API_TOKEN` is needed when `CARE_DEV_MODE=true`.

### Staging

```env
# .env — staging
POSTGRES_PASSWORD=staging-strong-password-here

CARE_API_TOKEN=staging-token-generate-with-openssl
CARE_CORS_ORIGINS=https://staging.your-domain.com
CARE_DEV_MODE=false

ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6

APP_ENV=staging
DEBUG=false
LOG_LEVEL=INFO

EATP_GENESIS_AUTHORITY=terrene.foundation
```

### Production

```env
# .env — production (values injected from secrets manager, not stored in file)
POSTGRES_PASSWORD=<from-secrets-manager>

CARE_API_TOKEN=<from-secrets-manager>
CARE_CORS_ORIGINS=https://your-domain.com
CARE_DEV_MODE=false
CARE_MAX_WS_SUBSCRIBERS=100

ANTHROPIC_API_KEY=<from-secrets-manager>
ANTHROPIC_MODEL=claude-sonnet-4-6

APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING

EATP_GENESIS_AUTHORITY=terrene.foundation
EATP_CREDENTIAL_TTL_SECONDS=300
```

In production, do not store the `.env` file on disk. Inject secrets through your cloud provider's secrets manager:

- AWS: Secrets Manager or Parameter Store
- Azure: Key Vault
- GCP: Secret Manager

---

## Security Recommendations

### Generating a secure API token

```bash
# Generate a cryptographically random 48-byte token (base64-encoded)
openssl rand -base64 48
```

Paste the output as the value of `CARE_API_TOKEN`.

### Database password strength

Use a password of at least 24 random characters. The default `care_dev_password` is intentionally weak and must be changed before any networked deployment.

```bash
# Generate a strong database password
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32
```

### Key rotation

LLM provider API keys should be rotated periodically. To rotate a key:

1. Generate a new key in the provider's dashboard.
2. Update the value in your secrets manager (or `.env` for development).
3. Restart the `api` service: `docker compose restart api`
4. Revoke the old key in the provider's dashboard.

### CORS configuration

In production, `CARE_CORS_ORIGINS` must list only the exact origins from which your frontend is served. Wildcard (`*`) is not accepted by the server — each origin must be explicit.

```env
CARE_CORS_ORIGINS=https://app.your-domain.com,https://admin.your-domain.com
```

### Protecting the database port

The `docker-compose.yml` exposes port 5432 to the host for local development tooling. In production, remove the `ports` entry from the `db` service so the database is only accessible within the `care_net` Docker network.

---

## Apache 2.0 License

Copyright 2026 Terrene Foundation

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
