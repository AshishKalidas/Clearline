import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AppRoutes } from '../App';
import { PreferencesProvider } from './Preferences';

beforeEach(() => {
  vi.stubEnv('MODE', 'test');
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  sessionStorage.clear();
  localStorage.clear();
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
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

it('keeps connected deep links inside the sample deployment and preserves the selected evidence tab', async () => {
  vi.stubEnv('MODE', 'demo');
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('No hosted API'));
  mount('/workspace/review/sample-split?tab=evidence');
  await screen.findByText('The evidence behind the proposal');
  expect(screen.getByRole('link', { name: /^Payment review/ })).toHaveAttribute(
    'href',
    '/sample/review',
  );
  expect(screen.queryByRole('link', { name: 'Connected workspace' })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('removes unavailable connected destinations from every sample entry point', async () => {
  vi.stubEnv('MODE', 'demo');
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('No hosted API'));
  const user = userEvent.setup();
  mount('/sample/settings');
  expect(screen.queryByRole('link', { name: /Open connected/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole('link', { name: /Data imports/ }));
  expect(screen.getByRole('link', { name: /Run the complete workspace/ })).toHaveAttribute(
    'href',
    'https://github.com/AshishKalidas/Clearline#run-the-complete-demo',
  );
  expect(screen.queryByRole('link', { name: /Open connected/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole('link', { name: /^Payment proofs/ }));
  expect(screen.queryByText(/Switch to Connected/)).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it.each(['/review', '/proofs'])('opens legacy %s links without a hosted API', async (path) => {
  vi.stubEnv('MODE', 'demo');
  const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('No hosted API'));
  mount(path);
  await screen.findByRole('heading', {
    name: path === '/review' ? 'Make the call. With evidence.' : 'Verify before you release.',
  });
  expect(screen.queryByRole('link', { name: 'Connected workspace' })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
