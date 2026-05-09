import { Download, Mail, RefreshCw, RotateCcw } from 'lucide-react';
import { buildFeedbackMailto } from '../desktopApi';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy, type Language } from '../lib/i18n';

export function SettingsPage() {
  const language = useDashboardStore((state) => state.language);
  const setLanguage = useDashboardStore((state) => state.setLanguage);
  const status = useDashboardStore((state) => state.desktopStatus);
  const startProduct = useDashboardStore((state) => state.startProduct);
  const restartProduct = useDashboardStore((state) => state.restartProduct);
  const stopProduct = useDashboardStore((state) => state.stopProduct);
  const checkForUpdates = useDashboardStore((state) => state.checkForUpdates);
  const installDesktopUpdate = useDashboardStore((state) => state.installDesktopUpdate);
  const installComponentUpdate = useDashboardStore((state) => state.installComponentUpdate);
  const rollbackComponents = useDashboardStore((state) => state.rollbackComponents);
  const loading = useDashboardStore((state) => state.loading);
  const t = copy[language].settings;
  const header = copy[language].header;
  const serviceName = (name: string) => {
    if (name === 'runtime') return t.serviceRuntime;
    if (name === 'adapter') return t.serviceAdapter;
    return t.serviceUi;
  };
  const serviceState = (state: string) => {
    if (state === 'healthy') return t.stateHealthy;
    if (state === 'blocked') return t.stateBlocked;
    if (state === 'unreachable') return t.stateUnreachable;
    return t.stateUnknown;
  };
  const updateLabel = (layer: string) => {
    if (layer === 'desktop_shell') return t.desktopApp;
    if (layer === 'local_components') return t.localComponents;
    return t.cloudPolicy;
  };
  const updateTone = (state: string) => {
    if (state === 'current') return 'success' as const;
    if (state === 'available') return 'warning' as const;
    if (state === 'blocked') return 'danger' as const;
    return 'neutral' as const;
  };

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>{t.services}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {(status?.services ?? []).map((service) => (
            <div key={service.name} className="flex items-center justify-between rounded-md border border-border bg-background p-3">
              <div>
                <p className="font-medium capitalize text-foreground">{serviceName(service.name)}</p>
                <p className="text-xs text-muted">{service.detail === 'Waiting for desktop host status.' ? t.waiting : service.detail}</p>
              </div>
              <Badge tone={service.state === 'healthy' ? 'success' : service.state === 'blocked' ? 'danger' : 'warning'}>{serviceState(service.state)}</Badge>
            </div>
          ))}
          <p className="text-xs text-muted">{header.controlsHint}</p>
          <div className="flex gap-2 pt-2"><Button onClick={() => void startProduct()}>{header.start}</Button><Button variant="secondary" onClick={() => void restartProduct()}>{header.restart}</Button><Button variant="ghost" onClick={() => void stopProduct()}>{header.stop}</Button></div>
        </CardContent>
      </Card>
      <div className="space-y-3">
        <Card>
          <CardHeader><CardTitle>{t.updates}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {(status?.updates ?? []).map((update) => (
              <div key={update.layer} className="rounded-md border border-border bg-background p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{updateLabel(update.layer)}</p>
                    <p className="font-mono text-xs text-muted">
                      {update.current_version}{update.available_version ? ` -> ${update.available_version}` : ''}
                    </p>
                  </div>
                  <Badge tone={updateTone(update.status)}>{update.status}</Badge>
                </div>
                <p className="mt-2 text-xs text-muted">{update.detail}</p>
              </div>
            ))}
            <div className="grid grid-cols-2 gap-2 pt-2">
              <Button variant="secondary" disabled={loading} onClick={() => void checkForUpdates()}><RefreshCw className="h-4 w-4" />{t.checkUpdates}</Button>
              <Button disabled={loading} onClick={() => void installDesktopUpdate()}><Download className="h-4 w-4" />{t.installApp}</Button>
              <Button variant="secondary" disabled={loading} onClick={() => void installComponentUpdate()}><Download className="h-4 w-4" />{t.installComponents}</Button>
              <Button variant="ghost" disabled={loading} onClick={() => void rollbackComponents()}><RotateCcw className="h-4 w-4" />{t.rollback}</Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t.language}</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            {(['en', 'zh'] as Language[]).map((item) => (
              <Button key={item} variant={language === item ? 'default' : 'secondary'} onClick={() => setLanguage(item)}>
                {item === 'en' ? t.english : t.chinese}
              </Button>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t.feedback}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted">{t.feedbackText}</p>
            <a href={status ? buildFeedbackMailto(status) : 'mailto:support@doloclaw.com'}><Button className="w-full"><Mail className="h-4 w-4" />{t.send}</Button></a>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
