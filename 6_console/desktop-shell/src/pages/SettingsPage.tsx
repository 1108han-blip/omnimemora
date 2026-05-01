import { Mail } from 'lucide-react';
import { buildFeedbackMailto } from '../desktopApi';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useDashboardStore } from '../store/useDashboardStore';

export function SettingsPage() {
  const status = useDashboardStore((state) => state.desktopStatus);
  const startProduct = useDashboardStore((state) => state.startProduct);
  const restartProduct = useDashboardStore((state) => state.restartProduct);
  const stopProduct = useDashboardStore((state) => state.stopProduct);

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>Local services</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(status?.services ?? []).map((service) => (
            <div key={service.name} className="flex items-center justify-between rounded-md border border-border bg-background p-3">
              <div>
                <p className="font-medium capitalize text-foreground">{service.name}</p>
                <p className="text-xs text-muted">{service.detail}</p>
              </div>
              <Badge tone={service.state === 'healthy' ? 'success' : service.state === 'blocked' ? 'danger' : 'warning'}>{service.state}</Badge>
            </div>
          ))}
          <div className="flex gap-2 pt-2"><Button onClick={() => void startProduct()}>Start</Button><Button variant="secondary" onClick={() => void restartProduct()}>Restart</Button><Button variant="ghost" onClick={() => void stopProduct()}>Stop</Button></div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Feedback packet</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">Feedback includes version, platform, service state, and update state. It does not upload prompts.</p>
          <a href={status ? buildFeedbackMailto(status) : 'mailto:support@doloclaw.com'}><Button className="w-full"><Mail className="h-4 w-4" />Send Feedback</Button></a>
        </CardContent>
      </Card>
    </div>
  );
}
