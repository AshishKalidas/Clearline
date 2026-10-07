import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, dateLabel, money, request } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('cent-safe display and authenticated requests', () => {
  it('formats integer cents without locale-dependent decimal behavior', () => {
    expect(money(370000)).toBe('R 3 700,00');
    expect(money(-12345)).toBe('−R 123,45');
    expect(money(1)).toBe('R 0,01');
    expect(() => money(1.1)).toThrow('integer cents');
    expect(dateLabel('2026-09-02')).toContain('2026');
  });
  it('adds reviewer and API key headers to a mutation', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    await request(
      '/proposals/example/approve',
      { method: 'POST', body: '{}' },
      { apiKey: 'offline-test-key', reviewer: 'Synthetic Reviewer' },
    );
    const [path, options] = fetch.mock.calls[0];
    expect(path).toBe('/api/proposals/example/approve');
    expect(options.headers.get('X-Reviewer')).toBe('Synthetic Reviewer');
    expect(options.headers.get('X-API-Key')).toBe('offline-test-key');
    expect(options.headers.get('Content-Type')).toBe('application/json');
  });
  it('preserves multipart boundaries and readable conflict errors', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response('{}'))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Already reviewed' }), { status: 409 }),
      );
    vi.stubGlobal('fetch', fetch);
    await request('/pops', { method: 'POST', body: new FormData() });
    expect(fetch.mock.calls[0][1].headers.has('Content-Type')).toBe(false);
    await expect(request('/proposals/example/approve', { method: 'POST' })).rejects.toMatchObject({
      status: 409,
      message: 'Already reviewed',
    });
    expect(new ApiError('Example', 422).status).toBe(422);
  });
});
