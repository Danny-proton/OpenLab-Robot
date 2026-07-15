export function corsHeaders(origin?: string | null): Record<string, string> {
  const allowedOrigin = origin || '*'
  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  }
}

export type CorsResolution = {
  allowed: boolean
  rejected: boolean
  headers: Record<string, string>
}

export async function resolveCors(
    origin?: string | null,
    _requestOrigin?: string | null,
    _options: Record<string, unknown> = {},
): Promise<CorsResolution> {
  return {
    allowed: true,
    rejected: false,
    headers: corsHeaders(origin),
  }
}