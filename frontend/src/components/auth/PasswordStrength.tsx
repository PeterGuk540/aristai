'use client';

import { cn } from '@/lib/utils';

interface PasswordStrengthProps {
  password: string;
}

export function PasswordStrength({ password }: PasswordStrengthProps) {
  const checks = [
    { label: '8+ characters', test: (p: string) => p.length >= 8 },
    { label: 'Uppercase', test: (p: string) => /[A-Z]/.test(p) },
    { label: 'Lowercase', test: (p: string) => /[a-z]/.test(p) },
    { label: 'Number', test: (p: string) => /[0-9]/.test(p) },
    { label: 'Special char', test: (p: string) => /[^A-Za-z0-9]/.test(p) },
  ];

  const passedCount = checks.filter((c) => c.test(password)).length;
  const strength = password.length === 0 ? 0 : passedCount;

  const getStrengthLabel = () => {
    if (strength === 0) return '';
    if (strength <= 2) return 'Weak';
    if (strength <= 3) return 'Fair';
    if (strength === 4) return 'Good';
    return 'Strong';
  };

  const getStrengthColor = () => {
    if (strength <= 2) return 'bg-red-500';
    if (strength <= 3) return 'bg-yellow-500';
    if (strength === 4) return 'bg-blue-500';
    return 'bg-green-500';
  };

  if (!password) return null;

  return (
    <div className="space-y-2">
      {/* Strength bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className={cn('h-full transition-all duration-300', getStrengthColor())}
            style={{ width: `${(strength / 5) * 100}%` }}
          />
        </div>
        <span
          className={cn(
            'text-xs font-medium',
            strength <= 2 && 'text-red-600 dark:text-red-400',
            strength === 3 && 'text-yellow-600 dark:text-yellow-400',
            strength === 4 && 'text-blue-600 dark:text-blue-400',
            strength === 5 && 'text-green-600 dark:text-green-400'
          )}
        >
          {getStrengthLabel()}
        </span>
      </div>

      {/* Requirements */}
      <div className="flex flex-wrap gap-2">
        {checks.map((check) => (
          <span
            key={check.label}
            className={cn(
              'text-xs px-2 py-0.5 rounded-full',
              check.test(password)
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500'
            )}
          >
            {check.label}
          </span>
        ))}
      </div>
    </div>
  );
}
