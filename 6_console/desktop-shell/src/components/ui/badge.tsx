import * as React from 'react';
import { cn } from '../../lib/utils';

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent';
const tones: Record<Tone, string> = {
  neutral: 'border-border bg-panel text-muted',
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  danger: 'border-danger/30 bg-danger/10 text-danger',
  accent: 'border-accent/40 bg-accent/10 text-[#AEB6FF]',
};

export function Badge({ className, tone = 'neutral', ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span className={cn('inline-flex h-5 items-center rounded border px-1.5 text-[10px] font-semibold uppercase tracking-wide', tones[tone], className)} {...props} />;
}
