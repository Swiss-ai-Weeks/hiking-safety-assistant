export class ApiError extends Error {
  status: number
  /** For a 503, which source could not answer (`swisstlm3d`, `demo`, …), when the body says. */
  source?: string

  constructor(status: number, message: string, source?: string) {
    super(message)
    this.status = status
    this.source = source
  }
}

/** Calls the backend. In dev Vite proxies `/api`; in production the backend serves the app itself. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { source?: unknown } | null
    const source = typeof body?.source === 'string' ? body.source : undefined
    throw new ApiError(response.status, `${init?.method ?? 'GET'} /api${path} failed (${response.status})`, source)
  }
  return response.json() as Promise<T>
}
