import type { Credentials } from './types';

/** Shared contract for HTTP and the isolated sample adapter. */
export type WorkspaceRequest = typeof request;

export interface CsvIssue {
  row: number;
  field: string | null;
  message: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly issues: CsvIssue[] = [],
    public readonly issueCount: number = issues.length,
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
      csvIssues(payload),
      typeof payload === 'object' &&
      payload !== null &&
      'issue_count' in payload &&
      typeof payload.issue_count === 'number'
        ? payload.issue_count
        : undefined,
    );
  }
  if (payload === null)
    throw new ApiError(
      'The workspace returned an unreadable response. Please retry.',
      response.status,
    );
  return payload as T;
}

function csvIssues(payload: unknown): CsvIssue[] {
  if (
    !payload ||
    typeof payload !== 'object' ||
    !('issues' in payload) ||
    !Array.isArray(payload.issues)
  )
    return [];
  return payload.issues.filter(
    (issue): issue is CsvIssue =>
      issue &&
      typeof issue === 'object' &&
      Number.isInteger(issue.row) &&
      (issue.field === null || typeof issue.field === 'string') &&
      typeof issue.message === 'string',
  );
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
