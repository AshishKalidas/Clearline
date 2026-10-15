import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { Invoice, Metrics, ProposalDetail } from '../types';
import { createSampleClient } from './sample';

const credentials = { apiKey: 'unused', reviewer: 'Synthetic Sample Reviewer' };
describe('isolated sample workspace', () => {
  it('simulates a review and resets without issuing any HTTP request', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network forbidden'));
    try {
      const client = createSampleClient();
      const before = await client.request<Metrics>('/metrics');
      const proposal = await client.request<ProposalDetail>('/proposals/sample-split');
      await client.request(
        '/proposals/sample-split/approve',
        { method: 'POST', body: '{}' },
        credentials,
      );
      const after = await client.request<Metrics>('/metrics');
      expect(after.proposals.pending).toBe(before.proposals.pending - 1);
      expect(after.bank_lines.matched).toBe(before.bank_lines.matched + 1);
      const invoices = await client.request<Invoice[]>('/invoices');
      expect(
        invoices.some(
          (invoice) => invoice.invoice_number === proposal.allocations[0].invoice_number,
        ),
      ).toBe(false);
      await expect(
        client.request(
          '/proposals/sample-split/approve',
          { method: 'POST', body: '{}' },
          credentials,
        ),
      ).rejects.toMatchObject({ status: 409 });
      client.reset();
      expect((await client.request<Metrics>('/metrics')).proposals.pending).toBe(
        before.proposals.pending,
      );
      expect(fetch).not.toHaveBeenCalled();
    } finally {
      fetch.mockRestore();
    }
  });
  it('rejects conflicting proof overrides and overdrawing corrections before state changes', async () => {
    const client = createSampleClient();
    await expect(
      client.request(
        '/proposals/sample-proof/approve',
        { method: 'POST', body: '{}' },
        credentials,
      ),
    ).rejects.toBeInstanceOf(ApiError);
    const original = await client.request<ProposalDetail>('/proposals/sample-match');
    await expect(
      client.request(
        '/proposals/sample-match/reject',
        {
          method: 'POST',
          body: JSON.stringify({
            note: 'Investigated',
            corrected_resolution: {
              ...original,
              allocations: [
                { invoice_number: original.allocations[0].invoice_number, amount_cents: 999999999 },
              ],
            },
          }),
        },
        credentials,
      ),
    ).rejects.toMatchObject({ status: 422 });
    expect((await client.request<ProposalDetail>('/proposals/sample-match')).status).toBe(
      'pending',
    );
    expect((await client.request<Metrics>('/metrics')).proposals.pending).toBe(8);
  });
});
