export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Calls the backend. In dev Vite proxies `/api`; in production the backend serves the app itself. */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
  if (!response.ok) throw new ApiError(response.status, `${init?.method ?? 'GET'} /api${path} failed (${response.status})`)
  return response.json() as Promise<T>
}
