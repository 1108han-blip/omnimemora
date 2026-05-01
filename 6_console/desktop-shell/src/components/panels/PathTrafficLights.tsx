import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import { copy, type Language } from '../../lib/i18n';

type Light = 'green' | 'red' | 'yellow';

export function buildPathStatus(status?: { bypass?: boolean; request_status?: string } | null): Record<string, Light> {
  if (!status) {
    return { agent: 'yellow', ingress: 'yellow', policy: 'yellow', memory: 'yellow', output: 'yellow' };
  }
  if (status.request_status === 'failed') {
    return { agent: 'green', ingress: 'red', policy: 'red', memory: 'red', output: 'red' };
  }
  if (status.bypass || status.request_status === 'bypassed') {
    return { agent: 'green', ingress: 'green', policy: 'yellow', memory: 'yellow', output: 'yellow' };
  }
  return { agent: 'green', ingress: 'green', policy: 'green', memory: 'green', output: 'green' };
}

export function PathTrafficLights({ status, language }: { status?: Record<string, Light>; language: Language }) {
  const t = copy[language].path;
  const steps = [
    { key: 'agent', label: t.agent },
    { key: 'ingress', label: t.ingress },
    { key: 'policy', label: t.policy },
    { key: 'memory', label: t.memory },
    { key: 'output', label: t.output },
  ] as const;

  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t.title}</p>
          <p className="text-xs text-muted">{t.detail}</p>
        </div>
        <Badge tone="accent">{t.module}</Badge>
      </div>
      <div className="grid grid-cols-5 gap-2 max-lg:grid-cols-1">
        {steps.map((step, index) => {
          const light = status?.[step.key] ?? 'yellow';
          return (
            <div key={step.key} className="relative rounded-md border border-border bg-surface p-2">
              <div className="flex items-center gap-2">
                <span className={cn('h-2.5 w-2.5 rounded-full', light === 'green' && 'bg-success', light === 'yellow' && 'bg-warning', light === 'red' && 'bg-danger')} />
                <span className="truncate text-xs font-medium text-foreground">{step.label}</span>
              </div>
              <p className="mt-1 font-mono text-[10px] text-muted">0{index + 1}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
