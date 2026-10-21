import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { ProofView } from './ProofView';
import { request } from './api';
import type { BankLine, PopResult } from './types';

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  request: vi.fn(),
}));

const credentials = { apiKey: 'offline', reviewer: 'Synthetic Reviewer' };
const notReceived: PopResult = {
  id: 'proof',
  filename: 'generated.pdf',
  verdict: 'not_received',
  extracted: {},
  checks: [{ check: 'bank_presence', passed: false }],
  matched_bank_line_id: null,
  summary: 'No matching payment has arrived. Do not release goods.',
};
const verified: PopResult = {
  ...notReceived,
  verdict: 'verified',
  matched_bank_line_id: 'older-bank-line',
  summary: 'Bank evidence supports this claim.',
  checks: [{ check: 'bank_presence', passed: true }],
};
const observation: BankLine = {
  id: 'older-bank-line',
  value_date: '2026-09-01',
  amount_cents: 12345,
  raw_reference: 'INV-100003',
  payer_name: 'Synthetic bank payer',
  payer_account_masked: '0042',
  status: 'matched',
};
const file = () => new File(['%PDF synthetic'], 'proof.pdf', { type: 'application/pdf' });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((finish) => {
    resolve = finish;
  });
  return { promise, resolve };
}
async function selectProof() {
  const user = userEvent.setup();
  await user.upload(screen.getByLabelText('Proof of payment PDF'), file());
  return user;
}
beforeEach(() => vi.mocked(request).mockReset());

it('uploads a claim and displays a not-received warning from real response data', async () => {
  vi.mocked(request).mockResolvedValue(notReceived);
  const onVerified = vi.fn();
  render(<ProofView credentials={credentials} onVerified={onVerified} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  await waitFor(() =>
    expect(
      screen.getByText('No matching payment has arrived. Do not release goods.'),
    ).toBeInTheDocument(),
  );
  expect(request).toHaveBeenCalledWith(
    '/pops',
    expect.objectContaining({ method: 'POST', body: expect.any(FormData) }),
    expect.objectContaining({ reviewer: 'Synthetic Reviewer' }),
  );
  expect(screen.getByText('Failed')).toBeInTheDocument();
  expect(onVerified).toHaveBeenCalledOnce();
});

it('locks the selected claim and prevents repeated writes until verification completes', async () => {
  const pending = deferred<PopResult>();
  vi.mocked(request).mockReturnValue(pending.promise);
  render(<ProofView credentials={credentials} onVerified={vi.fn()} />);
  const user = await selectProof();
  await user.type(screen.getByLabelText(/Claimed invoice/), ' inv-100003 ');
  const submit = screen.getByRole('button', { name: /Verify payment claim/ });
  act(() => {
    fireEvent.click(submit);
    fireEvent.click(submit);
  });
  expect(request).toHaveBeenCalledOnce();
  expect(screen.getByLabelText('Proof of payment PDF')).toBeDisabled();
  expect(screen.getByRole('button', { name: /proof.pdf/ })).toBeDisabled();
  expect(screen.getByLabelText(/Claimed invoice/)).toBeDisabled();
  const body = vi.mocked(request).mock.calls[0][1]!.body as FormData;
  expect(body.get('claimed_invoice_number')).toBe('INV-100003');
  expect(body.get('file')).toBeInstanceOf(File);
  await act(async () => pending.resolve(notReceived));
  expect(screen.getByRole('button', { name: /Verify payment claim/ })).toBeEnabled();
});

it('loads the exact bank observation and clears the result when the claim changes', async () => {
  vi.mocked(request).mockResolvedValueOnce(verified).mockResolvedValueOnce(observation);
  render(<ProofView credentials={credentials} onVerified={vi.fn()} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  expect(await screen.findByText(observation.payer_name)).toBeInTheDocument();
  expect(request).toHaveBeenLastCalledWith('/bank-lines/older-bank-line', {
    signal: expect.any(AbortSignal),
  });
  await user.type(screen.getByLabelText(/Claimed invoice/), 'INV-100006');
  expect(screen.queryByText(verified.summary)).not.toBeInTheDocument();
  expect(screen.queryByText(observation.payer_name)).not.toBeInTheDocument();
});

it('retains the saved verdict when supplementary bank evidence is unavailable', async () => {
  vi.mocked(request).mockResolvedValueOnce(verified).mockRejectedValueOnce(new Error('Offline'));
  const onVerified = vi.fn();
  render(<ProofView credentials={credentials} onVerified={onVerified} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('The verification was saved');
  expect(screen.getByText(verified.summary)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Verify payment claim/ })).toBeEnabled();
  expect(onVerified).toHaveBeenCalledOnce();
});

it('refreshes the workspace after an upload finishes following navigation without starting a read', async () => {
  const pending = deferred<PopResult>();
  vi.mocked(request).mockReturnValue(pending.promise);
  const onVerified = vi.fn();
  const { unmount } = render(<ProofView credentials={credentials} onVerified={onVerified} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  expect(vi.mocked(request).mock.calls[0][1]).not.toHaveProperty('signal');
  unmount();
  await act(async () => pending.resolve(verified));
  expect(onVerified).toHaveBeenCalledOnce();
  expect(request).toHaveBeenCalledOnce();
});

it('cancels the supplementary bank read when the proof view unmounts', async () => {
  const pending = deferred<BankLine>();
  vi.mocked(request).mockResolvedValueOnce(verified).mockReturnValueOnce(pending.promise);
  const { unmount } = render(<ProofView credentials={credentials} onVerified={vi.fn()} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  const signal = vi.mocked(request).mock.calls[1][1]!.signal!;
  expect(signal.aborted).toBe(false);
  expect(screen.getByRole('status')).toHaveTextContent('Loading linked bank evidence');
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => pending.resolve(observation));
});

it('does not report completion for a failed upload and allows a retry', async () => {
  vi.mocked(request).mockRejectedValueOnce(new Error('A valid X-API-Key is required'));
  const onVerified = vi.fn();
  render(<ProofView credentials={credentials} onVerified={onVerified} />);
  const user = await selectProof();
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('A valid X-API-Key is required');
  expect(onVerified).not.toHaveBeenCalled();
  vi.mocked(request).mockResolvedValueOnce(notReceived);
  await user.click(screen.getByRole('button', { name: /Verify payment claim/ }));
  expect(await screen.findByText(notReceived.summary)).toBeInTheDocument();
  expect(onVerified).toHaveBeenCalledOnce();
});
