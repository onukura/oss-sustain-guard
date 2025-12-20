/**
 * OSS Sustain Guard - Cloudflare Worker
 *
 * Provides shared cache for package sustainability analysis results.
 *
 * Endpoints:
 *   GET  /{key}              - Get single package data
 *   POST /batch              - Get multiple packages (JSON body: {"keys": [...]})
 *   PUT  /{key}              - Store single package (requires auth)
 *   PUT  /batch              - Store multiple packages (requires auth)
 *   GET  /history/{ecosystem}/{package} - List available dates for package
 *   GET  /history/{ecosystem}/{package}?from=YYYY-MM-DD&to=YYYY-MM-DD - Get historical data
 *
 * Key format: {schema_version}:{ecosystem}:{package_name}[:{date}]
 * Examples:
 *   - 2.0:python:requests (latest data)
 *   - 2.0:python:requests:2025-12-20 (historical snapshot)
 */

const CACHE_TTL = 3600; // 1 hour CDN cache
const KV_TTL = 31536000; // 365 days
const HISTORY_RETENTION_DAYS = 90; // Keep historical data for 90 days
const RATE_LIMIT_PER_MIN = 100;
const RATE_LIMIT_WINDOW = 60; // seconds
const MAX_KEY_LENGTH = 256; // Maximum key length
const MAX_BODY_SIZE = 1024 * 1024; // 1MB max body size
const BATCH_RATE_WEIGHT = 10; // Batch requests count as 10 normal requests

// Valid ecosystems for key validation (must match Python ECOSYSTEM_MAPPING values)
const VALID_ECOSYSTEMS = new Set([
  'python', 'javascript', 'rust', 'java', 'php', 'ruby', 'csharp', 'go', 'kotlin'
]);

// Key format regex: {version}:{ecosystem}:{package_name}[:{date}]
// Package names can include: letters, numbers, @, /, _, -, ., :
// Optional date suffix format: YYYY-MM-DD
// Note: Java packages use format like "com.google.guava:guava" (contains colons)
// Note: npm scoped packages use format like "@types/node"
const KEY_FORMAT_REGEX = /^[\d.]+:[a-z]+:[a-zA-Z0-9@/_.:%-]+(:\d{4}-\d{2}-\d{2})?$/;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Security headers for all responses
    const securityHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': "default-src 'none'",
      'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: securityHeaders });
    }

    // Check Content-Length for body requests (prevent oversized payloads)
    const contentLength = parseInt(request.headers.get('Content-Length') || '0');
    if (contentLength > MAX_BODY_SIZE) {
      return new Response(
        JSON.stringify({ error: 'Payload too large' }),
        {
          status: 413,
          headers: { ...securityHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    // Rate limiting with weighted batch requests
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    const rateLimitKey = `ratelimit:${clientIP}`;
    const isBatchRequest = path === '/batch';
    const weight = isBatchRequest ? BATCH_RATE_WEIGHT : 1;
    const rateLimited = await checkRateLimit(env.CACHE_KV, rateLimitKey, weight, ctx);

    if (rateLimited) {
      return new Response(
        JSON.stringify({ error: 'Rate limit exceeded. Try again later.' }),
        {
          status: 429,
          headers: {
            ...securityHeaders,
            'Content-Type': 'application/json',
            'Retry-After': String(RATE_LIMIT_WINDOW)
          }
        }
      );
    }

    try {
      // Route handling
      if (request.method === 'GET' && path.startsWith('/history/')) {
        return await handleHistoryGet(request, env, ctx, securityHeaders);
      }

      if (request.method === 'GET' && path !== '/batch') {
        return await handleGet(request, env, ctx, securityHeaders);
      }

      if (request.method === 'POST' && path === '/batch') {
        return await handleBatchGet(request, env, ctx, securityHeaders);
      }

      if (request.method === 'PUT' && path !== '/batch') {
        return await handlePut(request, env, ctx, securityHeaders);
      }

      if (request.method === 'PUT' && path === '/batch') {
        return await handleBatchPut(request, env, ctx, securityHeaders);
      }

      return new Response(
        JSON.stringify({ error: 'Not found' }),
        {
          status: 404,
          headers: { ...securityHeaders, 'Content-Type': 'application/json' }
        }
      );
    } catch (error) {
      console.error('Worker error:', error);
      return new Response(
        JSON.stringify({ error: 'Internal server error' }),
        {
          status: 500,
          headers: { ...securityHeaders, 'Content-Type': 'application/json' }
        }
      );
    }
  }
};

/**
 * Rate limiting check with weighted requests
 */
async function checkRateLimit(kv, key, weight, ctx) {
  const count = parseInt(await kv.get(key) || '0');

  if (count >= RATE_LIMIT_PER_MIN) {
    return true; // Rate limited
  }

  // Increment counter with weight and TTL
  ctx.waitUntil(
    kv.put(key, String(count + weight), { expirationTtl: RATE_LIMIT_WINDOW })
  );

  return false;
}

/**
 * Validate key format: {version}:{ecosystem}:{package_name}[:{date}]
 * Package name itself may contain colons (e.g., Java "com.google.guava:guava")
 * Optional date suffix in YYYY-MM-DD format
 */
function validateKey(key) {
  if (!key || key.length > MAX_KEY_LENGTH) {
    return { valid: false, error: 'Key length invalid' };
  }

  if (!KEY_FORMAT_REGEX.test(key)) {
    return { valid: false, error: 'Invalid key format' };
  }

  // Split only on first two colons to extract version and ecosystem
  // Format: {version}:{ecosystem}:{package_name_which_may_contain_colons}[:{date}]
  const firstColon = key.indexOf(':');
  const secondColon = key.indexOf(':', firstColon + 1);

  if (firstColon === -1 || secondColon === -1) {
    return { valid: false, error: 'Key must have format version:ecosystem:package[:date]' };
  }

  const ecosystem = key.substring(firstColon + 1, secondColon);
  if (!VALID_ECOSYSTEMS.has(ecosystem)) {
    return { valid: false, error: `Invalid ecosystem: ${ecosystem}` };
  }

  // Check if date suffix is present and valid
  const remainder = key.substring(secondColon + 1);
  const dateSuffixMatch = remainder.match(/:(\d{4}-\d{2}-\d{2})$/);
  if (dateSuffixMatch) {
    // Validate date format
    const dateStr = dateSuffixMatch[1];
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      return { valid: false, error: 'Invalid date format' };
    }
  }

  return { valid: true };
}

/**
 * GET /history/{ecosystem}/{package} - Get historical data
 * Query params:
 *   - from: Start date (YYYY-MM-DD) - optional
 *   - to: End date (YYYY-MM-DD) - optional
 *   - list: If present, only return list of available dates
 *
 * Returns:
 *   - If list=true: { "dates": ["2025-12-20", "2025-12-19", ...] }
 *   - Otherwise: { "2025-12-20": {...}, "2025-12-19": {...}, ... }
 */
async function handleHistoryGet(request, env, ctx, securityHeaders) {
  const url = new URL(request.url);
  const pathParts = url.pathname.split('/').filter(p => p);

  // Expected path: /history/{ecosystem}/{package}
  if (pathParts.length < 3) {
    return new Response(
      JSON.stringify({ error: 'Invalid path. Expected: /history/{ecosystem}/{package}' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  const ecosystem = pathParts[1];
  const packageName = decodeURIComponent(pathParts.slice(2).join('/'));

  // Validate ecosystem
  if (!VALID_ECOSYSTEMS.has(ecosystem)) {
    return new Response(
      JSON.stringify({ error: `Invalid ecosystem: ${ecosystem}` }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  // Parse query parameters
  const fromDate = url.searchParams.get('from');
  const toDate = url.searchParams.get('to');
  const listOnly = url.searchParams.has('list');

  // Get schema version (assume 2.0 for now, could be configurable)
  const schemaVersion = '2.0';
  const baseKey = `${schemaVersion}:${ecosystem}:${packageName}`;

  try {
    // List all keys with this prefix
    const listResult = await env.CACHE_KV.list({ prefix: `${baseKey}:` });

    // Extract dates from keys
    const dateRegex = /:(\d{4}-\d{2}-\d{2})$/;
    const availableDates = listResult.keys
      .map(item => {
        const match = item.name.match(dateRegex);
        return match ? match[1] : null;
      })
      .filter(date => date !== null)
      .sort()
      .reverse(); // Most recent first

    // Filter by date range if specified
    let filteredDates = availableDates;
    if (fromDate || toDate) {
      filteredDates = availableDates.filter(date => {
        if (fromDate && date < fromDate) return false;
        if (toDate && date > toDate) return false;
        return true;
      });
    }

    // If list only, return dates
    if (listOnly) {
      return new Response(
        JSON.stringify({ dates: filteredDates }),
        {
          headers: {
            ...securityHeaders,
            'Content-Type': 'application/json',
            'Cache-Control': `public, max-age=${CACHE_TTL}`
          }
        }
      );
    }

    // Fetch data for all filtered dates
    const historyData = {};
    await Promise.all(
      filteredDates.map(async (date) => {
        const key = `${baseKey}:${date}`;
        const value = await env.CACHE_KV.get(key);
        if (value) {
          historyData[date] = JSON.parse(value);
        }
      })
    );

    return new Response(
      JSON.stringify(historyData),
      {
        headers: {
          ...securityHeaders,
          'Content-Type': 'application/json',
          'Cache-Control': `public, max-age=${CACHE_TTL}`
        }
      }
    );
  } catch (error) {
    console.error('History fetch error:', error);
    return new Response(
      JSON.stringify({ error: 'Failed to fetch history' }),
      { status: 500, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * GET /{key} - Get single package data
 */
async function handleGet(request, env, ctx, securityHeaders) {
  const url = new URL(request.url);
  const key = decodeURIComponent(url.pathname.slice(1)); // Remove leading / and decode

  if (!key) {
    return new Response(
      JSON.stringify({ error: 'Key is required' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  // Validate key format
  const validation = validateKey(key);
  if (!validation.valid) {
    return new Response(
      JSON.stringify({ error: validation.error }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  // Check CDN cache first
  const cacheKey = new Request(url.toString(), request);
  const cache = caches.default;
  let response = await cache.match(cacheKey);

  if (response) {
    // Add security headers to cached response
    const newHeaders = new Headers(response.headers);
    Object.entries(securityHeaders).forEach(([k, v]) => newHeaders.set(k, v));
    return new Response(response.body, { headers: newHeaders });
  }

  // Fetch from KV
  const value = await env.CACHE_KV.get(key);

  if (!value) {
    return new Response(null, {
      status: 404,
      headers: securityHeaders
    });
  }

  // Create response with cache headers
  response = new Response(value, {
    headers: {
      ...securityHeaders,
      'Content-Type': 'application/json',
      'Cache-Control': `public, max-age=${CACHE_TTL}`
    }
  });

  // Store in CDN cache
  ctx.waitUntil(cache.put(cacheKey, response.clone()));

  return response;
}

/**
 * POST /batch - Get multiple packages
 * Body: { "keys": ["2.0:python:requests", "2.0:python:django", ...] }
 */
async function handleBatchGet(request, env, ctx, securityHeaders) {
  try {
    const body = await request.json();
    const keys = body.keys;

    if (!Array.isArray(keys) || keys.length === 0) {
      return new Response(
        JSON.stringify({ error: 'keys array is required' }),
        { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Limit batch size
    if (keys.length > 100) {
      return new Response(
        JSON.stringify({ error: 'Batch size limit: 100 keys' }),
        { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Validate all keys before processing
    for (const key of keys) {
      const validation = validateKey(key);
      if (!validation.valid) {
        return new Response(
          JSON.stringify({ error: `Invalid key "${key}": ${validation.error}` }),
          { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
        );
      }
    }

    // Fetch all keys in parallel
    const results = await Promise.all(
      keys.map(async (key) => {
        const value = await env.CACHE_KV.get(key);
        return [key, value ? JSON.parse(value) : null];
      })
    );

    // Convert to object
    const data = Object.fromEntries(results.filter(([_, v]) => v !== null));

    return new Response(
      JSON.stringify(data),
      {
        headers: {
          ...securityHeaders,
          'Content-Type': 'application/json',
          'Cache-Control': `public, max-age=${CACHE_TTL}`
        }
      }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: 'Invalid JSON body' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * PUT /{key} - Store single package (requires auth)
 */
async function handlePut(request, env, ctx, securityHeaders) {
  // Check authentication with timing-safe comparison
  const authHeader = request.headers.get('Authorization');
  const expectedAuth = `Bearer ${env.WRITE_SECRET}`;

  if (!authHeader || !timingSafeEqual(authHeader, expectedAuth)) {
    return new Response(
      JSON.stringify({ error: 'Unauthorized' }),
      { status: 401, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  const url = new URL(request.url);
  const key = decodeURIComponent(url.pathname.slice(1));

  if (!key) {
    return new Response(
      JSON.stringify({ error: 'Key is required' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  // Validate key format
  const validation = validateKey(key);
  if (!validation.valid) {
    return new Response(
      JSON.stringify({ error: validation.error }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  try {
    const body = await request.text();

    // Validate JSON and check size
    if (body.length > MAX_BODY_SIZE) {
      return new Response(
        JSON.stringify({ error: 'Payload too large' }),
        { status: 413, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
      );
    }

    JSON.parse(body);

    // Store in KV with TTL
    await env.CACHE_KV.put(key, body, { expirationTtl: KV_TTL });

    return new Response(
      JSON.stringify({ success: true, key }),
      { headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: 'Invalid JSON' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * Timing-safe string comparison to prevent timing attacks
 */
function timingSafeEqual(a, b) {
  if (a.length !== b.length) {
    return false;
  }

  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

/**
 * PUT /batch - Store multiple packages (requires auth)
 * Body: { "entries": { "key1": {...}, "key2": {...}, ... } }
 */
async function handleBatchPut(request, env, ctx, securityHeaders) {
  // Check authentication with timing-safe comparison
  const authHeader = request.headers.get('Authorization');
  const expectedAuth = `Bearer ${env.WRITE_SECRET}`;

  if (!authHeader || !timingSafeEqual(authHeader, expectedAuth)) {
    return new Response(
      JSON.stringify({ error: 'Unauthorized' }),
      { status: 401, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }

  try {
    const body = await request.json();
    const entries = body.entries;

    if (!entries || typeof entries !== 'object') {
      return new Response(
        JSON.stringify({ error: 'entries object is required' }),
        { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const keys = Object.keys(entries);

    // Limit batch size
    if (keys.length > 100) {
      return new Response(
        JSON.stringify({ error: 'Batch size limit: 100 entries' }),
        { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Validate all keys before processing
    for (const key of keys) {
      const validation = validateKey(key);
      if (!validation.valid) {
        return new Response(
          JSON.stringify({ error: `Invalid key "${key}": ${validation.error}` }),
          { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
        );
      }
    }

    // Store all entries in parallel
    await Promise.all(
      keys.map((key) =>
        env.CACHE_KV.put(
          key,
          JSON.stringify(entries[key]),
          { expirationTtl: KV_TTL }
        )
      )
    );

    return new Response(
      JSON.stringify({ success: true, written: keys.length }),
      { headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: 'Invalid JSON body' }),
      { status: 400, headers: { ...securityHeaders, 'Content-Type': 'application/json' } }
    );
  }
}
