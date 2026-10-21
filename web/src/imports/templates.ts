export type ImportKind = 'invoices' | 'bank-lines';
export interface ImportPreview {
  kind: ImportKind;
  row_count: number;
  columns: string[];
  rows: Record<string, string | number>[];
}
export interface ImportResult {
  inserted: number;
  skipped: number;
}

/** Fictional, paired examples that can be imported repeatedly without duplicate records. */
export const templates: Record<ImportKind, { label: string; csv: string }> = {
  invoices: {
    label: 'Invoices',
    csv: 'invoice_number,account_code,customer_name,notes,issue_date,due_date,amount_cents\nINV-980001,C-98001,Marula Sample Studio,Template example,2026-09-01,2026-09-30,125000\n',
  },
  'bank-lines': {
    label: 'Bank observations',
    csv: 'value_date,amount_cents,raw_reference,payer_name,payer_account_masked,bank_transaction_id\n2026-09-02,125000,INV-980001,Marula Sample Studio,0042,template-eft-980001\n',
  },
};
export const columnLabels: Record<string, string> = {
  invoice_number: 'Invoice',
  account_code: 'Customer account',
  customer_name: 'Customer',
  notes: 'Notes',
  issue_date: 'Issued',
  due_date: 'Due',
  amount_cents: 'Amount',
  value_date: 'Value date',
  raw_reference: 'Reference',
  payer_name: 'Payer',
  payer_account_masked: 'Account suffix',
  bank_transaction_id: 'Bank transaction ID',
};
