# Environment Setup Guide

## Quick Start

```bash
# 1. Copy the example environment file
cp .env.example .env

# 2. Edit .env with your actual values
nano .env

# 3. Verify configuration (optional)
npx prisma validate
```

## Required Variables

### Database
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://hermes:***@localhost:5432/thai_car_intelligence?schema=public` |
| `DB_USER` | Database username | `hermes` |
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `thai_car_intelligence` |

### Admin Authentication
| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_API_TOKEN` | Secret token for admin API access | `your-random-secret-here` |

## Optional Variables (Future Features)

### AI/LLM Provider
Leave blank to disable AI features (deterministic mode).

| Variable | Description | Example |
|----------|-------------|---------|
| `AI_PROVIDER` | Provider type | `openai-compatible` |
| `AI_BASE_URL` | API endpoint | `https://api.openai.com/v1` |
| `AI_API_KEY` | API key | `sk-...` |
| `AI_MODEL` | Model name | `gpt-4o` |
| `AI_SIMPLE_MODEL` | Model for simple tasks | `gpt-4o-mini` |
| `AI_COMPLEX_MODEL` | Model for complex reasoning | `gpt-4o` |
| `AI_FAST_FALLBACK_MODEL` | Fast fallback | `gpt-4o-mini` |

### Embedding (Vector Search)
| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_PROVIDER` | Provider type | (empty) |
| `EMBEDDING_BASE_URL` | API endpoint | (empty) |
| `EMBEDDING_MODEL` | Model name | (empty) |
| `EMBEDDING_DIMENSIONS` | Vector dimensions | `768` |
| `EMBEDDING_API_KEY` | API key | (empty) |

### Storage (Future)
| Variable | Description | Example |
|----------|-------------|---------|
| `STORAGE_PROVIDER` | Storage type | `s3` |
| `STORAGE_BUCKET` | Bucket name | `my-bucket` |
| `STORAGE_ENDPOINT` | Endpoint URL | `https://s3.amazonaws.com` |
| `STORAGE_REGION` | AWS region | `us-east-1` |
| `STORAGE_ACCESS_KEY_ID` | Access key | `AKIA...` |
| `STORAGE_SECRET_ACCESS_KEY` | Secret key | `wJal...` |

### Crawler
| Variable | Description | Default |
|----------|-------------|---------|
| `CRAWLER_USER_AGENT` | User agent string | `thai-car-intelligence-bot/0.1` |
| `CRAWLER_REQUEST_DELAY_MS` | Delay between requests | `1000` |
| `CRAWLER_MAX_CONCURRENCY` | Max parallel requests | `2` |
| `CRAWLER_TIMEOUT_MS` | Request timeout | `30000` |

## Validation

```bash
# Check Prisma schema
npx prisma validate

# Check TypeScript compilation
npx tsc --noEmit

# Run tests
npx vitest run
```

## Security Notes

- **NEVER commit `.env` or `.env.local` to git**
- **NEVER put real secrets in `.env.example`**
- Use strong, random values for `ADMIN_API_TOKEN`
- Rotate API keys regularly
- Use environment-specific `.env` files for different deployments

## Local Development Server

### Canonical Port: 3099

The local development server runs on **port 3099**. This is the standard port for all local development and testing.

### Starting the Dev Server

```bash
# From the project root
npx next dev -p 3099

# Or with admin token for admin routes
ADMIN_API_TOKEN=your-token npx next dev -p 3099
```

### Accessing the Application

- **Main app:** http://localhost:3099
- **Catalog:** http://localhost:3099/cars
- **AI Ask:** http://localhost:3099/ai-ask
- **Compare:** http://localhost:3099/compare
- **Admin moderation:** http://localhost:3099/admin/moderation

### Stopping the Dev Server

```bash
pkill -f "next dev -p 3099"
```

### Notes

- Port 3099 is used to avoid conflicts with other services (Docker containers on 3000, etc.)
- The dev server reads `.env` from the project root
- Hot reload is enabled by default
- API routes are available at `/api/*`
