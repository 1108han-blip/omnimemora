import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function ContextDebugPage() {
  const language = useDashboardStore((state) => state.language);
  const selectedRequestId = useDashboardStore((state) => state.selectedRequestId);
  const evidenceByRequestId = useDashboardStore((state) => state.evidenceByRequestId);
  const t = copy[language].context;
  const live = copy[language].live;
  const evidence = selectedRequestId ? evidenceByRequestId[selectedRequestId] : null;

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>{t.title}</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">{t.description}</p>
          {!evidence && <div className="rounded-md border border-border bg-background p-3 text-sm text-muted">{t.noSelection}</div>}
          {evidence && (
            <>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{live.before}</p><strong>{compactNumber(evidence.context.before_tokens)}</strong></div>
                <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{live.after}</p><strong>{compactNumber(evidence.context.after_tokens)}</strong></div>
                <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{live.saving}</p><strong className="text-success">{percent(evidence.context.savings_ratio)}</strong></div>
              </div>
              <pre className="max-h-72 overflow-auto rounded-md border border-border bg-background p-3 font-mono text-xs text-foreground">{evidence.context.selected_memories.map((memory) => memory.content || memory.abstract || memory.uri).join('\n\n') || live.notAvailable}</pre>
            </>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t.callChain}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {!evidence && <p className="text-sm text-muted">{t.noSelection}</p>}
          {evidence?.chain.nodes.map((node) => (
            <div key={node.id} className="grid grid-cols-[110px_1fr_70px] gap-2 rounded-md border border-border bg-background p-2 text-xs">
              <span className="font-mono text-muted">{node.label || node.id}</span>
              <span className="truncate text-foreground">{node.note}</span>
              <span className="text-right font-mono text-muted">{node.duration_ms.toFixed(1)}ms</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
