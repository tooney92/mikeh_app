/**
 * Single place the app talks to the FastAPI backend.
 *
 * In dev VITE_API_BASE_URL is empty, so paths stay relative ("/api/...") and
 * Vite's proxy forwards them. In a deployed build it holds the API origin.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

const TOKEN_KEY = 'tmglobal.accessToken'

export class ApiError extends Error {
  readonly status: number
  readonly path: string

  constructor(status: number, path: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.path = path
  }

  /** 401 — no valid token. The only status that should send you to /login. */
  get isUnauthenticated(): boolean {
    return this.status === 401
  }

  /** 403 — logged in, but not allowed. Never a reason to log someone out. */
  get isForbidden(): boolean {
    return this.status === 403
  }
}

/* --------------------------------------------------------------- token --- */

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * Fires when a request comes back 401, so the auth provider can drop the user
 * to the login screen from anywhere without every caller handling it.
 */
type UnauthenticatedHandler = () => void
let onUnauthenticated: UnauthenticatedHandler | null = null

export function setUnauthenticatedHandler(handler: UnauthenticatedHandler | null): void {
  onUnauthenticated = handler
}

/* ------------------------------------------------------------ requests --- */

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

export function apiSend<T>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

/**
 * FastAPI's `detail` is NOT always a string.
 *
 * A raise HTTPException(...) sends a string, but a 422 from request-body
 * validation sends an ARRAY of {loc, msg, type} objects. Passing that array
 * straight to `new Error(...)` renders it "[object Object]", so every
 * validation failure in the app used to surface as that — the one message
 * guaranteed to tell a user nothing and to send a developer to the wrong file.
 *
 * The `loc` array is dropped deliberately: it reads ["body", "minFitPercent"]
 * and naming the wire field in a user-facing string is noise, since the screen
 * already knows which control the user touched.
 */
function describeDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter((msg): msg is string => !!msg)
    if (messages.length > 0) return messages.join('. ')
  }
  return undefined
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')

  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers })

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`; fall back to the status text.
    const detail = await response
      .json()
      .then((body: { detail?: unknown }) => describeDetail(body.detail))
      .catch(() => undefined)

    // A dead token can surface on ANY request, not just /auth/me — the contract
    // notes a deactivated account 403s on its next call rather than at expiry.
    if (response.status === 401) {
      clearToken()
      onUnauthenticated?.()
    }

    throw new ApiError(response.status, path, detail ?? response.statusText)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
