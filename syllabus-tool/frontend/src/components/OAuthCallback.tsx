import { useEffect, useState } from 'react';
import { exchangeCodeForToken, checkAnyAuth } from '../lib/auth.ts';
import type { AuthUser } from '../lib/auth.ts';

interface OAuthCallbackProps {
  onSuccess: (user: AuthUser) => void;
  onError: (error: string) => void;
}

export function OAuthCallback({ onSuccess, onError }: OAuthCallbackProps) {
  const [status, setStatus] = useState('Completing sign-in...');

  useEffect(() => {
    const handle = async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get('code');

      if (!code) {
        onError('No authorization code found.');
        return;
      }

      const result = await exchangeCodeForToken(code);
      if (!result.success) {
        onError(result.error || 'Token exchange failed');
        return;
      }

      setStatus('Verifying session...');

      const user = await checkAnyAuth();
      if (user) {
        // Clean URL before signaling success
        window.history.replaceState({}, '', window.location.pathname);
        onSuccess(user);
      } else {
        onError('Failed to verify session after OAuth login.');
      }
    };

    handle();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="text-center">
        <svg className="animate-spin h-8 w-8 text-blue-600 mx-auto mb-4" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <p className="text-gray-600 text-sm">{status}</p>
      </div>
    </div>
  );
}
