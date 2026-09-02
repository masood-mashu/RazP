import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'default'
}) => {
  const getCardClass = () => {
    switch (variant) {
      case 'success':
        return 'metric-card metric-card-accent';
      case 'warning':
        return 'metric-card metric-card-warning';
      case 'danger':
        return 'metric-card metric-card-danger';
      default:
        return 'metric-card';
    }
  };

  const getIconColor = () => {
    switch (variant) {
      case 'success':
        return 'text-primary';
      case 'warning':
        return 'text-accent';
      case 'danger':
        return 'text-destructive';
      case 'info':
        return 'text-sky-400';
      default:
        return 'text-muted-foreground';
    }
  };

  return (
    <div className={getCardClass()} data-testid={`metric-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-start justify-between">
        <span className="eyebrow">{title}</span>
        <Icon size={16} className={getIconColor()} />
      </div>
      <div className="mt-3">
        <div className="mono-number text-[26px] font-medium tracking-[-0.06em] text-foreground leading-none">
          {value}
        </div>
        {subtitle && (
          <p className="mt-2 text-[11px] text-muted-foreground leading-tight">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
};
