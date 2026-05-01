interface TooltipPayload {
  name?: string;
  value?: number | string;
  color?: string;
}

export function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayload[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-panel px-2.5 py-2 text-xs text-foreground">
      <p className="mb-1 font-mono text-muted">{label}</p>
      <div className="space-y-1">
        {payload.map((item) => (
          <div key={`${item.name}-${item.value}`} className="flex items-center justify-between gap-4">
            <span>{item.name}</span>
            <span className="font-mono text-foreground">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
