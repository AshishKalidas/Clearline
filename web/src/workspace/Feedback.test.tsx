import { act, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Toast } from './Feedback';

afterEach(() => vi.useRealTimers());

it('dismisses on time after a parent update and calls the latest handler', () => {
  vi.useFakeTimers();
  const original = vi.fn();
  const latest = vi.fn();
  const { rerender } = render(<Toast message="Proposal approved" clear={original} />);
  act(() => vi.advanceTimersByTime(5000));
  rerender(<Toast message="Proposal approved" clear={latest} />);
  act(() => vi.advanceTimersByTime(500));
  expect(original).not.toHaveBeenCalled();
  expect(latest).toHaveBeenCalledOnce();
});

it('gives a new message its full lifetime and cancels dismissal on unmount', () => {
  vi.useFakeTimers();
  const clear = vi.fn();
  const { rerender, unmount } = render(<Toast message="Proposal approved" clear={clear} />);
  act(() => vi.advanceTimersByTime(5000));
  rerender(<Toast message="Proposal rejected" clear={clear} />);
  act(() => vi.advanceTimersByTime(5000));
  expect(clear).not.toHaveBeenCalled();
  unmount();
  act(() => vi.runAllTimers());
  expect(clear).not.toHaveBeenCalled();
});
