import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError, type WorkspaceRequest } from '../api';
import type { ImportPreview, ImportResult } from './templates';
import { useCsvImport } from './useCsvImport';

const credentials = { apiKey: 'synthetic-test-key', reviewer: 'Synthetic Reviewer' };
const preview: ImportPreview = {
  kind: 'invoices',
  row_count: 1,
  columns: ['amount_cents'],
  rows: [{ amount_cents: 125000 }],
};
const file = () => new File(['synthetic CSV'], 'invoices.csv', { type: 'text/csv' });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((finish) => {
    resolve = finish;
  });
  return { promise, resolve };
}
function mount(
  transport: (...args: Parameters<WorkspaceRequest>) => Promise<unknown>,
  enabled = true,
  onImported = vi.fn(),
) {
  // The test transport supplies decoded fixtures at the same boundary as the HTTP adapter.
  const request: WorkspaceRequest = async <T>(...args: Parameters<WorkspaceRequest>) =>
    (await transport(...args)) as T;
  return {
    ...renderHook(() => useCsvImport({ request, enabled, credentials, onImported })),
    onImported,
  };
}
afterEach(() => vi.useRealTimers());

it('binds confirmation to the validated file and clears it when the selection changes', async () => {
  const request = vi.fn<WorkspaceRequest>().mockResolvedValue(preview);
  const { result } = mount(request);
  act(() => result.current.selectFile(file()));
  await act(() => result.current.validate());
  await act(() => result.current.importFile());
  expect(request).toHaveBeenCalledOnce();
  act(() => result.current.confirm(true));
  const replacement = file();
  act(() => result.current.selectFile(replacement));
  expect(result.current.state).toEqual({
    phase: 'idle',
    kind: 'invoices',
    file: replacement,
    problem: null,
  });
  await act(() => result.current.importFile());
  expect(request).toHaveBeenCalledOnce();
  act(() => result.current.selectKind('bank-lines'));
  expect(result.current.state).toEqual({
    phase: 'idle',
    kind: 'bank-lines',
    file: null,
    problem: null,
  });
});

it('locks a preview synchronously so repeated events cannot issue duplicate requests or change its file', async () => {
  const pending = deferred<ImportPreview>();
  const request = vi.fn<WorkspaceRequest>().mockReturnValue(pending.promise);
  const { result } = mount(request);
  const selected = file();
  act(() => result.current.selectFile(selected));
  let finished!: Promise<void>;
  act(() => {
    finished = result.current.validate();
    void result.current.validate();
    result.current.selectFile(file());
    result.current.selectKind('bank-lines');
  });
  expect(request).toHaveBeenCalledOnce();
  expect(result.current.state).toMatchObject({
    phase: 'validating',
    kind: 'invoices',
    file: selected,
  });
  await act(async () => {
    pending.resolve(preview);
    await finished;
  });
  expect(result.current.state).toMatchObject({ phase: 'ready', preview, confirmed: false });
});

it('aborts an unfinished preview on navigation and does not report an import', async () => {
  const pending = deferred<ImportPreview>();
  const request = vi.fn<WorkspaceRequest>().mockReturnValue(pending.promise);
  const { result, unmount, onImported } = mount(request);
  act(() => result.current.selectFile(file()));
  let finished!: Promise<void>;
  act(() => {
    finished = result.current.validate();
  });
  const signal = request.mock.calls[0][1]?.signal;
  expect(signal?.aborted).toBe(false);
  unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    pending.resolve(preview);
    await finished;
  });
  expect(onImported).not.toHaveBeenCalled();
});

it('does not accept a late preview after its cancellation deadline', async () => {
  vi.useFakeTimers();
  const pending = deferred<ImportPreview>();
  const request = vi.fn<WorkspaceRequest>().mockReturnValue(pending.promise);
  const { result } = mount(request);
  act(() => result.current.selectFile(file()));
  let finished!: Promise<void>;
  act(() => {
    finished = result.current.validate();
  });
  act(() => vi.advanceTimersByTime(15000));
  expect(request.mock.calls[0][1]?.signal?.aborted).toBe(true);
  await act(async () => {
    pending.resolve(preview);
    await finished;
  });
  expect(result.current.state).toMatchObject({
    phase: 'idle',
    problem: { message: expect.stringContaining('too long') },
  });
  await act(() => result.current.importFile());
  expect(request).toHaveBeenCalledOnce();
});

it('lets one confirmed write finish after navigation and refreshes the workspace once', async () => {
  const pending = deferred<ImportResult>();
  const request = vi
    .fn<WorkspaceRequest>()
    .mockResolvedValueOnce(preview)
    .mockReturnValueOnce(pending.promise);
  const { result, unmount, onImported } = mount(request);
  act(() => result.current.selectFile(file()));
  await act(() => result.current.validate());
  act(() => result.current.confirm(true));
  let finished!: Promise<void>;
  act(() => {
    finished = result.current.importFile();
    void result.current.importFile();
  });
  expect(request).toHaveBeenCalledTimes(2);
  expect(request.mock.calls[1][1]?.signal).toBeUndefined();
  expect(result.current.state.phase).toBe('importing');
  unmount();
  await act(async () => {
    pending.resolve({ inserted: 1, skipped: 0 });
    await finished;
  });
  expect(onImported).toHaveBeenCalledOnce();
});

it('retains safe validation diagnostics and keeps failed writes explicitly retryable', async () => {
  const issue = { row: 2, field: 'amount_cents', message: 'Use integer cents.' };
  const request = vi
    .fn<WorkspaceRequest>()
    .mockRejectedValueOnce(new ApiError('Correct the CSV.', 422, [issue], 25))
    .mockResolvedValueOnce(preview)
    .mockRejectedValueOnce(new ApiError('Invoice conflicts with current data.', 422, [issue]));
  const { result, onImported } = mount(request);
  act(() => result.current.selectFile(file()));
  await act(() => result.current.validate());
  expect(result.current.state).toMatchObject({
    phase: 'idle',
    problem: { issues: [issue], issueCount: 25 },
  });
  await act(() => result.current.validate());
  act(() => result.current.confirm(true));
  await act(() => result.current.importFile());
  expect(result.current.state).toMatchObject({
    phase: 'ready',
    preview,
    confirmed: true,
    problem: { message: 'Invoice conflicts with current data.' },
  });
  expect(onImported).not.toHaveBeenCalled();
});

it('cannot send preview or import requests while the workspace is disabled', async () => {
  const request = vi.fn<WorkspaceRequest>();
  const { result } = mount(request, false);
  act(() => result.current.selectFile(file()));
  await act(() => result.current.validate());
  act(() => result.current.confirm(true));
  await act(() => result.current.importFile());
  expect(request).not.toHaveBeenCalled();
});
