import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function compactNumber(value: number | null | undefined) {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Math.max(0, Math.round(value ?? 0)));
}

export function percent(value: number | null | undefined) {
  if (!Number.isFinite(value ?? Number.NaN)) return '0%';
  const normalized = Math.abs(value as number) <= 1 ? (value as number) * 100 : (value as number);
  return `${Math.round(normalized)}%`;
}

export function timeShort(value: string | null | undefined) {
  if (!value) return 'never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
