import type { RequestEvidence } from './types';

export const SUPPORT_EMAIL = 'support@doloclaw.com';
const UI_VERSION = '5173-feedback-v1';

function bodyLine(label: string, value: string): string {
  return `${label}: ${value}`;
}

export function buildFeedbackMailto(evidence: RequestEvidence | null): string {
  const subject = evidence
    ? `OmniMemora Request Feedback ${evidence.request.request_id}`
    : 'OmniMemora Beta Feedback';

  const platform = typeof navigator !== 'undefined' ? navigator.userAgent || 'unknown' : 'unknown';
  const lines = [
    bodyLine('version', UI_VERSION),
    bodyLine('platform', platform),
    bodyLine('request_id', evidence?.request.request_id ?? ''),
    bodyLine('error_code', evidence?.status.error_code ?? ''),
    bodyLine('agent_family', evidence?.request.agent_family ?? ''),
    bodyLine('request_status', evidence?.status.request_status ?? ''),
    bodyLine('query_summary', evidence?.request.query_summary ?? ''),
    'steps:',
    '- ',
  ];

  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`;
}
