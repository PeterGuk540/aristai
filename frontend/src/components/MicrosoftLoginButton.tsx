'use client';

import { getMicrosoftLoginUrl } from '@/lib/ms-auth';

interface MicrosoftLoginButtonProps {
  className?: string;
  disabled?: boolean;
}

export function MicrosoftLoginButton({ className = '', disabled = false }: MicrosoftLoginButtonProps) {
  const handleMicrosoftLogin = () => {
    // Redirect to Cognito Hosted UI with Microsoft as identity provider
    const loginUrl = getMicrosoftLoginUrl();
    window.location.href = loginUrl;
  };

  return (
    <button
      type="button"
      onClick={handleMicrosoftLogin}
      disabled={disabled}
      className={`w-full flex items-center justify-center gap-3 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg shadow-sm bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${className}`}
    >
      {/* Microsoft Logo SVG */}
      <svg className="w-5 h-5" viewBox="0 0 23 23">
        <path fill="#f35325" d="M1 1h10v10H1z"/>
        <path fill="#81bc06" d="M12 1h10v10H12z"/>
        <path fill="#05a6f0" d="M1 12h10v10H1z"/>
        <path fill="#ffba08" d="M12 12h10v10H12z"/>
      </svg>
      <span className="font-medium">Continue with Microsoft</span>
    </button>
  );
}
