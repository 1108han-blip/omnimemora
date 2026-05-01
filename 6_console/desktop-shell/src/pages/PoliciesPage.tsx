import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function PoliciesPage() {
  const language = useDashboardStore((state) => state.language);
  const policies = useDashboardStore((state) => state.policies);
  const setPolicy = useDashboardStore((state) => state.setPolicy);
  const t = copy[language].policies;

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t.title}</CardTitle><Badge tone="warning">{t.candidate}</Badge></CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border border-border bg-background p-3">
            <div className="mb-2 flex items-center justify-between"><p className="text-sm font-medium text-foreground">{t.compression}</p><span className="font-mono text-xs text-muted">{policies.compressionLevel}%</span></div>
            <Input type="range" min={0} max={100} value={policies.compressionLevel} onChange={(event) => setPolicy('compressionLevel', Number(event.target.value))} className="px-0" />
          </div>
          <label className="flex items-center justify-between rounded-md border border-border bg-background p-3">
            <div><p className="text-sm font-medium text-foreground">{t.fallback}</p><p className="text-xs text-muted">{t.fallbackText}</p></div>
            <Input className="h-4 w-4" type="checkbox" checked={policies.fallbackEnabled} onChange={(event) => setPolicy('fallbackEnabled', event.target.checked)} />
          </label>
          <label className="flex items-center justify-between rounded-md border border-border bg-background p-3">
            <div><p className="text-sm font-medium text-foreground">{t.aggressive}</p><p className="text-xs text-muted">{t.aggressiveText}</p></div>
            <Input className="h-4 w-4" type="checkbox" checked={policies.aggressiveMode} onChange={(event) => setPolicy('aggressiveMode', event.target.checked)} />
          </label>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t.rules}</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm text-muted">
          <p>{t.rule1}</p>
          <p>{t.rule2}</p>
          <Button className="w-full" variant="secondary">{t.save}</Button>
        </CardContent>
      </Card>
    </div>
  );
}
