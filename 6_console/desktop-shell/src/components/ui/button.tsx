import * as React from 'react';
import { cn } from '../../lib/utils';

type Variant = 'default' | 'secondary' | 'ghost' | 'danger';

const variants: Record<Variant, string> = {
  default: 'border-accent/50 bg-accent/15 text-foreground hover:bg-accent/25',
  secondary: 'border-border bg-panel text-foreground hover:bg-[#172131]',
  ghost: 'border-transparent bg-transparent text-muted hover:bg-panel hover:text-foreground',
  danger: 'border-danger/50 bg-danger/10 text-danger hover:bg-danger/15',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: 'sm' | 'md' | 'icon';
}

export function Button({ className, variant = 'default', size = 'md', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md border font-medium transition disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' && 'h-8 px-2.5 text-xs',
        size === 'md' && 'h-9 px-3 text-sm',
        size === 'icon' && 'h-8 w-8 p-0',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
