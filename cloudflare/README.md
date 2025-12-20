
# Cloudflare Worker - OSS Sustain Guard Cache

Shared cache system for package analysis results using Cloudflare Workers + KV.

## 📋 Prerequisites

- [Cloudflare account](https://dash.cloudflare.com/sign-up) (free plan is fine)
- [Node.js](https://nodejs.org/) 18 or later
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/install-and-update/)

## 🚀 Setup

### 1. Install Wrangler

```bash
npm install -g wrangler
```

### 2. Log in to Cloudflare

```bash
wrangler login
```

### 3. Create KV Namespace

```bash
# For production
wrangler kv namespace create "CACHE_KV"

# For staging (optional)
wrangler kv namespace create "CACHE_KV" --preview
```

Set the output Namespace ID to the `id` field in `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "CACHE_KV"
id = "your_kv_namespace_id"  # ← Replace this
```

### 4. Set Write Secret

```bash
# Generate a random secret
openssl rand -base64 32

# Set the secret in the Worker
wrangler secret put WRITE_SECRET
# Enter the above secret at the prompt
```

### 5. Deploy the Worker

#### Option A: Manual Deployment (for testing)

```bash
cd cloudflare
wrangler deploy
```

#### Option B: GitHub Actions (recommended for production)

The Worker is automatically deployed via GitHub Actions when:
- Changes are pushed to `cloudflare/` directory on `main` branch
- Manually triggered from Actions tab

**Setup GitHub Secrets:**

1. Generate a Cloudflare API Token:
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
   - Click "Create Token" → "Edit Cloudflare Workers" template
   - Set permissions: **Account Settings:Read**, **Workers Scripts:Edit**
   - Copy the generated token

2. Add secrets to GitHub repository:
   - Go to **Settings** → **Secrets and variables** → **Actions**
   - Add `CLOUDFLARE_API_TOKEN` with the token from step 1
   - Add `CF_WRITE_SECRET` (the same secret from step 4)

3. Trigger deployment:
   - Push changes to `cloudflare/` directory, or
   - Go to **Actions** → **Deploy Cloudflare Worker** → **Run workflow**

After a successful deployment, the Worker URL will be displayed in the workflow logs:

```
Published oss-sustain-guard-cache (1.23 sec)
  https://oss-sustain-guard-cache.{your-account}.workers.dev
```

Record this URL (used by the Python client and GitHub Actions).

---

## 🔌 API Endpoints

### GET `/{key}` - Get a single package

```bash
curl https://your-worker.workers.dev/2.0:python:requests
```

**Response**:
```json
{
  "ecosystem": "python",
  "package_name": "requests",
  "github_url": "https://github.com/psf/requests",
  "metrics": [...],
  ...
}
```

### POST `/batch` - Get multiple packages in batch

```bash
curl -X POST https://your-worker.workers.dev/batch \
  -H "Content-Type: application/json" \
  -d '{"keys": ["2.0:python:requests", "2.0:python:django"]}'
```

**Response**:
```json
{
  "2.0:python:requests": { ... },
  "2.0:python:django": { ... }
}
```

### PUT `/{key}` - Write a single package (authentication required)

```bash
curl -X PUT https://your-worker.workers.dev/2.0:python:requests \
  -H "Authorization: Bearer YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"ecosystem": "python", "package_name": "requests", ...}'
```

### PUT `/batch` - Batch write (authentication required)

```bash
curl -X PUT https://your-worker.workers.dev/batch \
  -H "Authorization: Bearer YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "entries": {
      "2.0:python:requests": {...},
      "2.0:python:django": {...}
    }
  }'
```

---

## 🔒 Security

### Rate Limiting

- **Limit**: 100 requests/min per IP
- **Implementation**: KV-based counter (60s TTL)

### Authentication

- **Read**: No authentication required (public cache)
- **Write**: `Authorization: Bearer {WRITE_SECRET}` required

### Cache Strategy

```
Request
   ↓
CDN Cache (1 hour) ← reduces KV reads
   ↓ (cache miss)
Cloudflare KV (365 days TTL)
```

---

## 📊 Free Tier Limits

| Resource         | Free Tier   | Usage Assumption                  |
|------------------|------------|-----------------------------------|
| Worker requests  | 100,000/day | Mostly absorbed by CDN cache      |
| KV reads         | 100,000/day | Efficient with batch API          |
| KV writes        | 1,000/day   | Only diffs written by CI/CD       |
| KV storage       | 1GB         | Sufficient (per package)          |

---

## 🧪 Local Development

```bash
# Start development server
wrangler dev

# Test in another terminal
curl http://localhost:8787/2.0:python:requests
```

---

## 🚀 CI/CD Integration

The Cloudflare Worker is automatically deployed via GitHub Actions (`.github/workflows/deploy-cloudflare.yml`).

**Required GitHub Secrets:**

| Secret | Description | How to Get |
|--------|-------------|------------|
| `CLOUDFLARE_API_TOKEN` | API token for Wrangler deployment | Cloudflare Dashboard → Profile → API Tokens → Create Token (use "Edit Cloudflare Workers" template) |
| `CF_WRITE_SECRET` | Write authentication secret for PUT endpoints | Same secret set in step 4 above (`openssl rand -base64 32`) |

**Deployment Triggers:**
- Automatic: Push to `main` branch with changes in `cloudflare/` directory
- Manual: GitHub Actions → "Deploy Cloudflare Worker" → "Run workflow"

**Deployment Flow:**
```
Push to main (cloudflare/*)
   ↓
GitHub Actions workflow
   ↓
Install Wrangler → Deploy Worker → Verify
   ↓
Live at workers.dev URL
```

---

## 🔧 Troubleshooting

### Check KV Namespace ID

```bash
wrangler kv namespace list
```

### Check Secrets

```bash
# List (values not shown)
wrangler secret list
```

### Check Logs

```bash
wrangler tail
```

---

## 📚 References

- [Cloudflare Workers Documentation](https://developers.cloudflare.com/workers/)
- [Cloudflare KV Documentation](https://developers.cloudflare.com/kv/)
- [Wrangler CLI Reference](https://developers.cloudflare.com/workers/wrangler/commands/)
