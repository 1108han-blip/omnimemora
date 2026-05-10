import { useState } from 'react';
import type {
  CoreCapabilitiesResponse,
  CoreCapabilitiesTrendResponse,
  RealRequestsCard,
  ContextCompressionCard,
  MemoryEnhancementCard,
  TokenSavingsCard,
} from '../types';

interface HeroMetricsProps {
  data: CoreCapabilitiesResponse | null;
  trendData: CoreCapabilitiesTrendResponse | null;
}

type CardType = 'real_requests' | 'context_compression' | 'memory_enhancement' | 'token_savings';

interface CardConfig {
  id: CardType;
  label: string;
}

const CARD_CONFIGS: CardConfig[] = [
  { id: 'real_requests', label: 'Real Requests' },
  { id: 'context_compression', label: 'Context Compression' },
  { id: 'memory_enhancement', label: 'Memory Enhancement' },
  { id: 'token_savings', label: 'Real Input Savings' },
];

function formatRatioPct(ratio: number): string {
  const safeRatio = Math.max(0, Math.min(1, Number.isFinite(ratio) ? ratio : 0));
  if (safeRatio >= 1) {
    return '100%';
  }
  const rounded = Math.round(safeRatio * 1000) / 10; // one decimal
  const capped = Math.min(99.9, rounded);
  return Number.isInteger(capped) ? `${capped.toFixed(0)}%` : `${capped.toFixed(1)}%`;
}

function formatSavedTokens(value: number): string {
  if (value > 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toLocaleString();
}

function FrontCard({ card, data }: { card: CardConfig; data: CoreCapabilitiesResponse }) {
  if (card.id === 'real_requests') {
    const c = data.cards.real_requests as RealRequestsCard;
    return (
      <div className="text-center">
        <div className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{card.label}</div>
        <div className="text-4xl font-bold mt-2 text-blue-600">{c.count.toLocaleString()}</div>
        <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
          {Math.round(c.ratio * 100)}% of observed
        </div>
      </div>
    );
  }

  if (card.id === 'context_compression') {
    const c = data.cards.context_compression as ContextCompressionCard;
    return (
      <div className="text-center">
        <div className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{card.label}</div>
        <div className="text-4xl font-bold mt-2 text-purple-600">
          {Math.round(c.ratio * 100)}%
        </div>
        <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
          {c.baseline_tokens.toLocaleString()} → {c.actual_tokens.toLocaleString()}
        </div>
      </div>
    );
  }

  if (card.id === 'memory_enhancement') {
    const c = data.cards.memory_enhancement as MemoryEnhancementCard;
    return (
      <div className="text-center">
        <div className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{card.label}</div>
        <div className="text-4xl font-bold mt-2 text-emerald-600">
          {Math.round(c.rate * 100)}%
        </div>
        <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
          {c.memory_count.toLocaleString()} memories packed
        </div>
      </div>
    );
  }

  // token_savings
  const c = data.cards.token_savings as TokenSavingsCard;
  return (
    <div className="text-center">
      <div className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{card.label}</div>
      <div className="text-4xl font-bold mt-2 text-amber-600">
        {formatSavedTokens(c.saved_tokens)}
      </div>
      <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
        {formatRatioPct(c.ratio)} full forwarded-payload delta
      </div>
    </div>
  );
}

function BackCard({ card, trend }: { card: CardConfig; trend: CoreCapabilitiesTrendResponse }) {
  const points = trend.trend;
  if (points.length === 0) {
    return <div className="text-xs text-zinc-400 py-4 text-center">暂无趋势数据</div>;
  }

  if (card.id === 'real_requests') {
    const rawValues = points.map(p => (p.real_requests as RealRequestsCard).count);
    const maxVal = Math.max(...rawValues, 1);
    const total7d = rawValues.reduce((s, v) => s + v, 0);
    return (
      <div className="text-center">
        <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">{total7d.toLocaleString()} total (7d)</div>
        <div className="flex items-end gap-0.5 h-20 mb-1">
          {points.map((pt) => {
            const val = (pt.real_requests as RealRequestsCard).count;
            return (
              <div key={pt.date} className="flex-1 flex flex-col items-center gap-0.5">
                <div className="w-full flex flex-col items-center justify-end h-full">
                  <div
                    className="w-full rounded-t bg-blue-400 dark:bg-blue-600"
                    style={{ height: `${Math.max((val / maxVal) * 100, 2)}%` }}
                    title={val.toString()}
                  />
                </div>
                <div className="text-[9px] text-zinc-400">{pt.date.slice(5)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (card.id === 'context_compression') {
    const rawValues = points.map(p => (p.context_compression as ContextCompressionCard).ratio);
    const maxVal = Math.max(...rawValues, 1);
    return (
      <div className="text-center">
        <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">compression ratio / day</div>
        <div className="flex items-end gap-0.5 h-20 mb-1">
          {points.map((pt) => {
            const val = (pt.context_compression as ContextCompressionCard).ratio;
            return (
              <div key={pt.date} className="flex-1 flex flex-col items-center gap-0.5">
                <div className="w-full flex flex-col items-center justify-end h-full">
                  <div
                    className="w-full rounded-t bg-purple-400 dark:bg-purple-600"
                    style={{ height: `${Math.max((val / maxVal) * 100, 2)}%` }}
                    title={val.toString()}
                  />
                </div>
                <div className="text-[9px] text-zinc-400">{pt.date.slice(5)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (card.id === 'memory_enhancement') {
    const rawValues = points.map(p => (p.memory_enhancement as MemoryEnhancementCard).memory_count);
    const maxVal = Math.max(...rawValues, 1);
    const total7d = rawValues.reduce((s, v) => s + v, 0);
    return (
      <div className="text-center">
        <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">{total7d.toLocaleString()} mems (7d)</div>
        <div className="flex items-end gap-0.5 h-20 mb-1">
          {points.map((pt) => {
            const val = (pt.memory_enhancement as MemoryEnhancementCard).memory_count;
            return (
              <div key={pt.date} className="flex-1 flex flex-col items-center gap-0.5">
                <div className="w-full flex flex-col items-center justify-end h-full">
                  <div
                    className="w-full rounded-t bg-emerald-400 dark:bg-emerald-600"
                    style={{ height: `${Math.max((val / maxVal) * 100, 2)}%` }}
                    title={val.toString()}
                  />
                </div>
                <div className="text-[9px] text-zinc-400">{pt.date.slice(5)}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // token_savings
  const rawValues = points.map(p => (p.token_savings as TokenSavingsCard).ratio);
  const maxVal = Math.max(...rawValues, 1);
  const total7d = points.reduce((s, pt) => s + ((pt.token_savings as TokenSavingsCard).saved_tokens || 0), 0);
  return (
    <div className="text-center">
      <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">
        {total7d > 1000 ? `${(total7d / 1000).toFixed(1)}K` : total7d.toLocaleString()} saved (7d)
      </div>
      <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">real input ratio/day</div>
      <div className="flex items-end gap-0.5 h-20 mb-1">
        {points.map((pt) => {
          const val = (pt.token_savings as TokenSavingsCard).ratio;
          return (
            <div key={pt.date} className="flex-1 flex flex-col items-center gap-0.5">
              <div className="w-full flex flex-col items-center justify-end h-full">
                <div
                  className="w-full rounded-t bg-amber-400 dark:bg-amber-600"
                  style={{ height: `${Math.max((val / maxVal) * 100, 2)}%` }}
                  title={val.toString()}
                />
              </div>
              <div className="text-[9px] text-zinc-400">{pt.date.slice(5)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function HeroMetrics({ data, trendData }: HeroMetricsProps) {
  const [flippedIndex, setFlippedIndex] = useState<number | null>(null);

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 animate-pulse">
            <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-20 mb-3" />
            <div className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {CARD_CONFIGS.map((card, i) => {
        const isFlipped = flippedIndex === i;
        return (
          <button
            key={card.id}
            onClick={() => setFlippedIndex(prev => (prev === i ? null : i))}
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 text-center shadow-sm hover:shadow-md cursor-pointer transition-all duration-300"
          >
            {!isFlipped && <FrontCard card={card} data={data} />}
            {isFlipped && trendData && (
              <div>
                <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-2">{card.label} — 7d</div>
                <BackCard card={card} trend={trendData} />
              </div>
            )}
            {isFlipped && !trendData && (
              <div className="text-xs text-zinc-400">趋势数据加载中...</div>
            )}
          </button>
        );
      })}
    </div>
  );
}
