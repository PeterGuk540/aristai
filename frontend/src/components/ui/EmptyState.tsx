import { type LucideIcon } from 'lucide-react';
import { type ReactNode } from 'react';

interface EmptyStateProps {
  icon: LucideIcon;
  message: string;
  submessage?: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, message, submessage, action }: EmptyStateProps) {
  return (
    <div className="flex items-start gap-3 py-6 text-neutral-500 dark:text-neutral-400">
      <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
      <div>
        <p>{message}</p>
        {submessage && <p className="text-sm mt-1">{submessage}</p>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}
