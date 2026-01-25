'use client';

import { Suspense, useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { exchangeCodeForToken, storeTokens, parseJwt } from '@/lib/auth';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('Processing...');
  const processedRef = useRef(false);

  useEffect(() => {
    // Prevent double execution in React Strict Mode
    if (processedRef.current) return;

    const handleCallback = async () => {
      // Check for error in URL
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');
      if (errorParam) {
        setError(errorDescription || errorParam);
        return;
      }

      // Get authorization code
      const code = searchParams.get('code');

      // If no code yet, wait a bit and check again (searchParams might not be ready)
      if (!code) {
        setTimeout(() => {
          const urlCode = new URLSearchParams(window.location.search).get('code');
          if (!urlCode) {
            setError('No authorization code received');
          }
        }, 500);
        return;
      }

      processedRef.current = true;
      setStatus('Exchanging code for tokens...');

      try {
        // Exchange code for tokens
        const redirectUri = `${window.location.origin}/callback`;
        const tokens = await exchangeCodeForToken(code, redirectUri);

        setStatus('Storing tokens...');

        // Parse the ID token to get username
        const payload = parseJwt(tokens.id_token);
        const username = payload?.sub || payload?.['cognito:username'] || 'user';

        // Store tokens in localStorage
        storeTokens(tokens, username);

        setStatus('Success! Redirecting...');

        // Redirect to home page
        router.push('/');
      } catch (err) {
        console.error('Token exchange error:', err);
        setError(err instanceof Error ? err.message : 'Failed to complete sign in');
      }
    };

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center max-w-md p-6">
          <div className="text-red-500 text-5xl mb-4">!</div>
          <h1 className="text-2xl font-bold text-red-600 mb-4">Authentication Error</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <p className="text-gray-600">{status}</p>
      </div>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading...</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <CallbackContent />
    </Suspense>
  );
}
