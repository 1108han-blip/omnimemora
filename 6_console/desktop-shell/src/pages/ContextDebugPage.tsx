import { useMemo, useState } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/input';

const seed = 'Use remembered client preferences, current product boundaries, and recent validation state to answer the operator without exposing ports as normal user steps.';

export function ContextDebugPage() {
  const [input, setInput] = useState(seed);
  const [ran, setRan] = useState(true);
  const result = useMemo(() => {
    const before = Math.max(120, input.length * 4);
    const after = Math.round(before * 0.58);
    return { before, after, saved: before - after, packed: `memory.boundary: 5173 is control/display, 18011 is opt-in ingress, 8765 is internal.\nmemory.release: desktop beta uses explicit update and rollback.\nrequest: ${input}` };
  }, [input]);

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>Compile simulation input</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Textarea value={input} onChange={(event) => setInput(event.target.value)} />
          <Button onClick={() => setRan(true)}>Run compile simulation</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Packed context and diff</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">Before</p><strong>{result.before}</strong></div>
            <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">After</p><strong>{result.after}</strong></div>
            <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">Saved</p><strong className="text-success">{result.saved}</strong></div>
          </div>
          <pre className="min-h-64 overflow-auto rounded-md border border-border bg-background p-3 font-mono text-xs text-foreground">{ran ? result.packed : 'Run simulation to produce packed context.'}</pre>
        </CardContent>
      </Card>
    </div>
  );
}
