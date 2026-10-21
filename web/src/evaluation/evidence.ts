import snapshot from '../generated/evidence.json';

export const providers = [
  { id: 'stub', name: 'Scripted baseline' },
  { id: 'claude', name: 'Claude' },
  { id: 'mimo', name: 'MiMo' },
] as const;
export type Provider = (typeof providers)[number]['id'];
export interface EvaluationReport {
  provider: string;
  model: string;
  baseline: boolean;
  retrieval_enabled: boolean;
  embedder: string;
  database: string;
  created_at: string;
  seed: number;
  dataset_sha256: string;
  counts: Record<string, number>;
  metrics: Record<string, number | null>;
  scenarios: Record<string, { correct: number; total: number }>;
  gates: Record<string, boolean>;
  passed: boolean;
  invariant_errors: string[];
  failure_count: number;
  agent_protocol_sha256?: string | null;
  live_configuration?: {
    gateway: string;
    upstream_provider: string;
  } | null;
}
export interface PublishedRun {
  provider: string;
  retrieval_enabled: boolean;
  report: EvaluationReport | null;
  report_sha256: string | null;
}
/** Generated and validated from repository reports; independent of workspace fixtures and API health. */
export const published: { schema_version: number; runs: PublishedRun[] } = snapshot;
export function findRun(provider: Provider, retrieval: boolean): PublishedRun {
  const run = published.runs.find(
    (item) => item.provider === provider && item.retrieval_enabled === retrieval,
  );
  if (!run) throw new Error('The published evaluation snapshot is incomplete.');
  return run;
}
export const metricDefinitions = [
  {
    key: 'incomplete_investigations',
    label: 'Incomplete investigations',
    format: 'number',
    note: 'Provider failures, exhausted limits or missing/invalid terminal proposals.',
  },
  {
    key: 'model_api_cost_usd',
    label: 'Measured model API cost',
    format: 'currency',
    note: 'Provider-reported USD for this run; unknown billing remains unmeasured.',
  },
  {
    key: 'agent_decision_accuracy',
    label: 'Agent decision accuracy',
    format: 'percent',
    note: 'Decision and invoice set agree with the label; agent cases only.',
  },
  {
    key: 'false_allocation_rate',
    label: 'Wrong automatic allocations',
    format: 'percent',
    note: 'Incorrect agent auto allocations divided by all agent auto allocations.',
  },
  {
    key: 'rules_precision',
    label: 'Exact-rule precision',
    format: 'percent',
    note: 'Correct rule matches divided by observed rule-match audit events.',
  },
  {
    key: 'escalation_recall',
    label: 'Required escalation recall',
    format: 'percent',
    note: 'Cases that require escalation and were escalated.',
  },
  {
    key: 'injection_resistance',
    label: 'Injection resistance',
    format: 'percent',
    note: 'Injected cases that did not propose an attacker-target invoice.',
  },
  {
    key: 'pop_verdict_accuracy',
    label: 'Payment-proof verdict accuracy',
    format: 'percent',
    note: 'Exact verdict agreement across the synthetic proof documents.',
  },
  {
    key: 'mean_latency_ms',
    label: 'Mean investigation latency',
    format: 'latency',
    note: 'Measured loop time per investigation on the evaluation machine.',
  },
  {
    key: 'mean_prompt_tokens',
    label: 'Mean prompt tokens',
    format: 'number',
    note: 'Reported provider input usage per investigation.',
  },
  {
    key: 'mean_completion_tokens',
    label: 'Mean completion tokens',
    format: 'number',
    note: 'Reported provider output usage per investigation.',
  },
  {
    key: 'retrieval_lift',
    label: 'Retrieval lift',
    format: 'points',
    note: 'Accuracy difference between compatible retrieval-on/off runs.',
  },
] as const;
export function metricValue(report: EvaluationReport | null, key: string, format: string): string {
  if (!report) return 'Not yet run';
  const value = report.metrics[key];
  if (value === null || value === undefined) return 'Not measured';
  if (key === 'false_allocation_rate' && report.counts.auto_applied === 0)
    return 'No auto allocations';
  if (format === 'percent') return `${(value * 100).toFixed(2)}%`;
  if (format === 'points') return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;
  if (format === 'latency') return `${value.toFixed(2)} ms`;
  if (format === 'currency') return `$${value.toFixed(6)}`;
  return value.toLocaleString('en-ZA', { maximumFractionDigits: 2 });
}
export const gateLabels: Record<string, string> = {
  rules_precision: 'Exact rules remain precise',
  false_allocation_rate: 'Automatic allocation error budget',
  escalation_recall: 'Required cases reach a reviewer',
  injection_resistance: 'Injected references stay contained',
  pop_verdict_accuracy: 'Proof verdicts agree with labels',
  forged_pop_recall: 'Absent and altered claims are caught',
  safety_invariants: 'Ledger and audit invariants hold',
  completed_investigations: 'Investigations finish within their bounds',
};
export function measuredDate(value: string): string {
  return new Intl.DateTimeFormat('en-ZA', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Africa/Johannesburg',
  }).format(new Date(value));
}
