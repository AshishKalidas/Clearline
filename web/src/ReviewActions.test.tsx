import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { ReviewActions } from './ReviewActions';
import type { ProposalDetail } from './types';
import { request } from './api';

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  request: vi.fn(),
}));
export const detail: ProposalDetail = {
  id: 'proposal-fixture',
  bank_line: {
    id: 'bank-fixture',
    amount_cents: 370000,
    payer_name: 'Lumen Synthetic Workshop',
    payer_account_masked: '0042',
    raw_reference: 'INV-100003',
    value_date: '2026-09-02',
    status: 'in_review',
  },
  decision: 'match',
  allocations: [{ invoice_number: 'INV-100003', amount_cents: 370000 }],
  confidence: 0.96,
  reasoning: 'Unique customer and amount evidence.',
  risk_flags: [],
  status: 'pending',
  policy_reason: 'customer has no prior resolved case',
  evidence: [],
  reviewer: null,
  review_note: null,
  model: 'stub-baseline-v1',
  steps: 6,
  latency_ms: 22,
  prompt_tokens: 0,
  completion_tokens: 0,
  trace: [],
  linked_pops: [],
};
beforeEach(() => vi.mocked(request).mockReset());

it('requires a note for rejection and supports the R shortcut', async () => {
  const onDecision = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ReviewActions detail={detail} busy={false} onDecision={onDecision} />);
  await user.keyboard('r');
  expect(screen.getByRole('button', { name: 'Reject proposal' })).toBeDisabled();
  await user.type(screen.getByLabelText('Review note'), 'Payer evidence needs investigation');
  await user.click(screen.getByRole('button', { name: 'Reject proposal' }));
  expect(onDecision).toHaveBeenCalledWith(
    'reject',
    'Payer evidence needs investigation',
    undefined,
  );
});

it('uses the approval shortcut only outside editable fields', async () => {
  const onDecision = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ReviewActions detail={detail} busy={false} onDecision={onDecision} />);
  await user.type(screen.getByLabelText('Review note'), 'a');
  expect(onDecision).not.toHaveBeenCalled();
  await user.click(document.body);
  await user.keyboard('a');
  expect(onDecision).toHaveBeenCalledWith('approve', 'a', undefined);
});

it('saves a correction as a human resolution with a required rationale', async () => {
  vi.mocked(request).mockResolvedValue([
    {
      id: 'invoice',
      invoice_number: 'INV-100006',
      customer_name: 'Aster Synthetic Workshop',
      outstanding_cents: 370000,
    },
  ]);
  const onDecision = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<ReviewActions detail={detail} busy={false} onDecision={onDecision} />);
  await user.click(screen.getByRole('button', { name: /Correct/ }));
  await waitFor(() =>
    expect(screen.getByRole('option', { name: /INV-100006/ })).toBeInTheDocument(),
  );
  await user.selectOptions(screen.getByLabelText('Corrected invoice 1'), 'INV-100006');
  await user.type(
    screen.getByLabelText('Review note'),
    'Verified the intended invoice independently',
  );
  await user.click(screen.getByRole('button', { name: 'Save corrected resolution' }));
  expect(onDecision).toHaveBeenCalledWith(
    'reject',
    'Verified the intended invoice independently',
    expect.objectContaining({
      decision: 'match',
      allocations: [{ invoice_number: 'INV-100006', amount_cents: 370000 }],
    }),
  );
});

it('requires an explicit note before a proof mismatch override', async () => {
  const onDecision = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(
    <ReviewActions
      detail={{
        ...detail,
        linked_pops: [
          {
            id: 'proof',
            filename: 'synthetic.pdf',
            verdict: 'mismatch',
            checks: [],
            summary: 'Amount differs',
            extracted: {},
            matched_bank_line_id: 'bank-fixture',
          },
        ],
      }}
      busy={false}
      onDecision={onDecision}
    />,
  );
  await user.click(screen.getByRole('button', { name: /Approve proposal/ }));
  expect(screen.getByRole('alert')).toHaveTextContent('Add a review note');
  expect(onDecision).not.toHaveBeenCalled();
});
