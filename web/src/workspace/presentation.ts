import type { Decision } from '../types';
export const decisionLabels: Record<Decision, string> = {
  match: 'Full match',
  partial: 'Partial payment',
  split: 'Split payment',
  overpayment: 'Overpayment',
  duplicate: 'Possible duplicate',
  escalate: 'Escalation',
};
export const eventLabels: Record<string, string> = {
  human_approved: 'Proposal approved',
  human_rejected: 'Proposal reviewed',
  policy_decision: 'Policy checked',
  resolution_applied: 'Resolution recorded',
  rules_match: 'Exact match found',
  rules_matched: 'Exact match found',
  reversal_applied: 'Reversal processed',
  pop_verified: 'Payment proof checked',
  proposal_submitted: 'Proposal prepared',
  invoices_ingested: 'Invoices imported',
  bank_lines_ingested: 'Bank lines imported',
};
export function clockLabel(value: string | Date): string {
  return new Intl.DateTimeFormat('en-ZA', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'Africa/Johannesburg',
  }).format(new Date(value));
}
