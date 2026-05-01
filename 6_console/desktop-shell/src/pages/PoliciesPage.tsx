import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function PoliciesPage() {
  const language = useDashboardStore((state) => state.language);
  const t = copy[language].policies;

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t.title}</CardTitle>
          <Badge tone="warning">{t.candidate}</Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium text-foreground">{t.active}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">{t.activeText}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium text-foreground">{t.local}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">{t.localText}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium text-foreground">{t.cloud}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted">{t.cloudText}</p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t.rules}</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm text-muted">
          <p>{t.rule1}</p>
          <p>{t.rule2}</p>
          <div className="rounded-md border border-border bg-panel p-3 text-xs text-warning">{t.unavailable}</div>
        </CardContent>
      </Card>
    </div>
  );
}
