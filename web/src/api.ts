import type { Credentials } from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

/** Read from the same-origin proxy; credentials accompany mutations only. */
export async function request<T>(
  path: string,
  options: RequestInit = {},
  credentials?: Credentials,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (credentials) {
    headers.set('X-API-Key', credentials.apiKey);
    headers.set('X-Reviewer', credentials.reviewer);
  }
  if (options.body && !(options.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...options, headers });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? payload.detail
        : null;
    throw new ApiError(
      typeof detail === 'string' ? detail : `Request failed (${response.status}). Please retry.`,
      response.status,
    );
  }
  if (payload === null)
    throw new ApiError(
      'The workspace returned an unreadable response. Please retry.',
      response.status,
    );
  return payload as T;
}

/** Monetary state remains integer cents, including display formatting. */
export function money(cents: number): string {
  if (!Number.isSafeInteger(cents)) throw new Error('Money must be integer cents');
  const amount = Math.abs(cents);
  const whole = Math.floor(amount / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${cents < 0 ? '−' : ''}R ${whole},${(amount % 100).toString().padStart(2, '0')}`;
}

export function dateLabel(date: string): string {
  return new Intl.DateTimeFormat('en-ZA', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Africa/Johannesburg',
  }).format(new Date(`${date}T12:00:00+02:00`));
}
