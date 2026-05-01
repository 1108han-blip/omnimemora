import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { useDashboardStore } from '../store/useDashboardStore';

export function PoliciesPage() {
  const policies = useDashboardStore((state) => state.policies);
  const setPolicy = useDashboardStore((state) => state.setPolicy);

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between"><CardTitle>Editable policy candidate</CardTitle><Badge tone="warning">candidate only</Badge></CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border border-border bg-background p-3">
            <div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium text-foreground">Compression level</p><span className="font-mono text-xs text-muted">{policies.compressionLevel}%</span></div>
            <Input type="range" min={0} max={100} value={policies.compressionLevel} onChange={(event) => setPolicy('compressionLevel', Number(event.target.value))} className="px-0" />
          </div>
          <label className="flex items-center justify-between rounded-md border border-border bg-background p-3">
            <div><p className="text-sm font-medium text-foreground">Fallback enabled</p><p className="text-xs text-muted">Fallback when memory confidence is weak.</p></div>
            <Input className="h-4 w-4" type="checkbox" checked={policies.fallbackEnabled} onChange={(event) => setPolicy('fallbackEnabled', event.target.checked)} />
          </label>
          <label className="flex items-center justify-between rounded-md border border-border bg-background p-3">
            <div><p className="text-sm font-medium text-foreground">Aggressive mode</p><p className="text-xs text-muted">Higher compression, higher review risk. Not default.</p></div>
            <Input className="h-4 w-4" type="checkbox" checked={policies.aggressiveMode} onChange={(event) => setPolicy('aggressiveMode', event.target.checked)} />
          </label>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Policy promotion rules</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm text-muted">
          <p>Cloud policy remains candidate-only. It is visible here, but never silently overrides local active policy.</p>
          <p>Promotion requires user confirmation and must not enter request hot path until accepted.</p>
          <Button className="w-full" variant="secondary">Save Candidate</Button>
        </CardContent>
      </Card>
    </div>
  );
}
