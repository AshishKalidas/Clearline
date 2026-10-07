import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { ProofView } from './ProofView';
import { request } from './api';

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  request: vi.fn(),
}));

it('uploads a claim and displays a not-received warning from real response data', async () => {
  vi.mocked(request).mockResolvedValue({
    id: 'proof',
    filename: 'generated.pdf',
    verdict: 'not_received',
    extracted: {},
    checks: [{ check: 'bank_presence', passed: false }],
    matched_bank_line_id: null,
    summary: 'No matching payment has arrived. Do not release goods.',
  });
  const user = userEvent.setup();
  render(<ProofView credentials={{ apiKey: 'offline', reviewer: 'Synthetic Reviewer' }} />);
  await user.upload(
    screen.getByLabelText('Proof of payment PDF'),
    new File(['%PDF synthetic'], 'proof.pdf', { type: 'application/pdf' }),
  );
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
});
