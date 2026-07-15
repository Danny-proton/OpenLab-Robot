export type H5RequestKind = 'local-trusted' | 'internal-sdk' | 'h5-browser'
export type H5RequestContext = {
  clientAddress: string | null
}

export function classifyH5Request(
    _request: Request,
    _url: URL,
    _context: H5RequestContext,
): H5RequestKind {
  return 'local-trusted'
}

export function shouldRequireH5Token(_opts: {
  request: Request
  url: URL
  h5Enabled: boolean
  context: H5RequestContext
}): boolean {
  return false
}

export function shouldBlockDisabledH5Access(_opts: {
  request: Request
  url: URL
  h5Enabled: boolean
  explicitAuthRequired: boolean
  context: H5RequestContext
}): boolean {
  return false
}