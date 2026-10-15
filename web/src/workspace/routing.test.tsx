import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AppRoutes } from '../App';
import { PreferencesProvider } from './Preferences';

beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());
function mount(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <PreferencesProvider>
        <AppRoutes />
      </PreferencesProvider>
    </MemoryRouter>,
  );
}
it('opens a sample deep link, navigates tabs and keeps all requests in the browser', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Offline'));
  const user = userEvent.setup();
  mount('/sample/review/sample-split?tab=evidence');
  await screen.findByText('The evidence behind the proposal');
  await user.click(screen.getByRole('tab', { name: 'Overview' }));
  await screen.findByText('R 3 700,00', { selector: '.bank-amount' });
  await user.click(screen.getByRole('tab', { name: 'Audit trail' }));
  await screen.findByText('Every decision, recorded.');
  expect(fetch).not.toHaveBeenCalled();
});
it('shows a recoverable 404 for a missing payment without substituting another proposal', async () => {
  mount('/sample/review/missing');
  await screen.findByText('Payment unavailable');
  expect(screen.queryByRole('button', { name: /Approve proposal/ })).not.toBeInTheDocument();
});
it('renders a not-found route and a useful return path', () => {
  mount('/sample/unknown-page');
  expect(screen.getByRole('heading', { name: 'A small wrong turn.' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Back to overview/ })).toHaveAttribute(
    'href',
    '/sample/overview',
  );
});
it('switches to the actual HTTP source and shows an offline state instead of sample values', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('API unavailable'));
  const user = userEvent.setup();
  mount('/sample/overview');
  await screen.findByText('R 39 280,00');
  await user.click(screen.getByRole('link', { name: 'Connected workspace' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('API unavailable'));
  expect(screen.queryByText('R 39 280,00')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith('/api/healthz', expect.anything());
});
