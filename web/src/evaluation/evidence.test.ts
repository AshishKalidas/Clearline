import { expect, it } from 'vitest';
import { findRun, metricValue } from './evidence';

it('keeps missing live runs unmeasured instead of substituting baseline results', () => {
  expect(metricValue(null, 'agent_decision_accuracy', 'percent')).toBe('Not yet run');
  const live = findRun('claude', true).report;
  if (live) expect(live.baseline).toBe(false);
});

it('distinguishes zero observed errors from having no automatic allocations to evaluate', () => {
  const report = findRun('stub', true).report!;
  expect(metricValue(report, 'false_allocation_rate', 'percent')).toBe('0.00%');
  expect(
    metricValue(
      { ...report, counts: { ...report.counts, auto_applied: 0 } },
      'false_allocation_rate',
      'percent',
    ),
  ).toBe('No auto allocations');
  expect(metricValue(report, 'not_measured', 'number')).toBe('Not measured');
  expect(
    metricValue(
      { ...report, metrics: { model_api_cost_usd: 0.00123456 } },
      'model_api_cost_usd',
      'currency',
    ),
  ).toBe('$0.001235');
});
