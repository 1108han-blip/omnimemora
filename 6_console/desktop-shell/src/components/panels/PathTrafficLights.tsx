import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';

const steps = [
  { key: 'agent', label: 'Agent' },
  { key: 'ingress', label: '18011 Ingress' },
  { key: 'policy', label: 'Policy' },
  { key: 'memory', label: '8765 Memory' },
  { key: 'runtime', label: 'Compiled Output' },
] as const;

type Light = 'green' | 'yellow' | 'red';

export function PathTrafficLights({ status }: { status?: Partial<Record<(typeof steps)[number]['key'], Light>> }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Product Path Traffic Lights</p>
          <p className="text-xs text-muted">Agent request path inside OmniMemora, not a user setup checklist.</p>
        </div>
        <Badge tone="accent">5173 module</Badge>
      </div>
      <div className="grid grid-cols-5 gap-2 max-lg:grid-cols-1">
        {steps.map((step, index) => {
          const light = status?.[step.key] ?? 'green';
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
