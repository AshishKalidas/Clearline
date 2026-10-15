export type Decision = 'match' | 'partial' | 'split' | 'overpayment' | 'duplicate' | 'escalate';
export interface Allocation {
  invoice_number: string;
  amount_cents: number;
}
export interface BankLine {
  id: string;
  value_date: string;
  amount_cents: number;
  raw_reference: string;
  payer_name: string;
  payer_account_masked: string;
  status: string;
}
export interface Proposal {
  id: string;
  bank_line: BankLine;
  decision: Decision;
  allocations: Allocation[];
  confidence: number;
  reasoning: string;
  risk_flags: string[];
  status: string;
  policy_reason: string;
  evidence: string[];
  reviewer: string | null;
  review_note: string | null;
  model: string;
  steps: number;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
}
export interface ToolPayload {
  step?: number;
  citation?: string;
  tool?: string;
  arguments?: unknown;
  result?: unknown;
}
export interface AuditEvent {
  id: string;
  event_type: string;
  actor: string;
  created_at: string;
  payload: ToolPayload & Record<string, unknown>;
}
export interface ProposalDetail extends Proposal {
  trace: AuditEvent[];
  linked_pops: PopResult[];
}
export interface Invoice {
  id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string;
  account_code: string;
  issue_date: string;
  due_date: string;
  amount_cents: number;
  outstanding_cents: number;
  status: string;
}
export interface Metrics {
  bank_lines: Record<string, number>;
  proposals: Record<string, number>;
  auto_apply_rate: number;
  mean_latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  provider: string;
  retrieval_enabled: boolean;
}
export interface Credentials {
  apiKey: string;
  reviewer: string;
}
export interface Resolution {
  decision: Decision;
  allocations: Allocation[];
  confidence: number;
  reasoning: string;
  evidence: string[];
  risk_flags: string[];
}
export interface PopCheck {
  check: string;
  passed: boolean;
  claimed?: string | number;
  observed?: string | number;
}
export interface PopResult {
  id: string;
  filename: string;
  verdict: 'verified' | 'not_received' | 'mismatch' | 'unreadable';
  extracted: Record<string, string | number>;
  checks: PopCheck[];
  matched_bank_line_id: string | null;
  summary: string;
}

export interface ActivityEvent {
  id: string;
  event_type: string;
  actor: string;
  created_at: string;
  bank_line_id: string | null;
  proposal_id: string | null;
  payer_name: string | null;
  amount_cents: number | null;
}

export type WorkspaceMode = 'sample' | 'connected';
