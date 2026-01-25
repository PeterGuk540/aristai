'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { exchangeCodeForToken as googleExchangeCode, getGoogleUserInfo } from '@/lib/google-auth';
import { exchangeCodeForToken as msExchangeCode, getMicrosoftUserInfo } from '@/lib/ms-auth';
import { api } from '@/lib/api';

function OAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      // Get the authorization code from URL
      const code = searchParams.get('code');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Handle error from OAuth provider
      if (errorParam) {
        setError(errorDescription || errorParam || 'Authentication failed');
        setIsProcessing(false);
        return;
      }

      // Check if code exists
      if (!code) {
        setError('No authorization code received');
        setIsProcessing(false);
        return;
      }

      try {
        // Exchange code for tokens
        // Both Google and Microsoft use the same Cognito token endpoint
        // The storeTokens function in each module checks the identity provider from the token
        // and sets the appropriate auth marker

        // Try Google exchange first (this will also work for Microsoft,
        // but will only set GoogleAuthUser marker if provider is Google)
        let result = await googleExchangeCode(code);

        // Check if this was a Google login
        let googleUser = getGoogleUserInfo();
        if (result.success && googleUser) {
          // Register or get user in the database
          try {
            await api.registerOrGetUser({
              name: googleUser.name || googleUser.email.split('@')[0],
              email: googleUser.email,
              auth_provider: 'google',
              cognito_sub: googleUser.sub,
            });
          } catch (apiError) {
            console.error('Failed to register user in database:', apiError);
          }
          router.replace('/courses');
          return;
        }

        // If Google exchange didn't identify a Google user, try Microsoft exchange
        // This will properly set the MicrosoftAuthUser marker
        result = await msExchangeCode(code);

        if (result.success) {
          const msUser = getMicrosoftUserInfo();
          if (msUser) {
            try {
              await api.registerOrGetUser({
                name: msUser.name || msUser.email.split('@')[0],
                email: msUser.email,
                auth_provider: 'microsoft',
                cognito_sub: msUser.sub,
              });
            } catch (apiError) {
              console.error('Failed to register user in database:', apiError);
            }
            router.replace('/courses');
            return;
          }

          // Success but no user info - still redirect
          router.replace('/courses');
          return;
        }

        // Exchange failed
        setError(result.error || 'Failed to exchange code for tokens');
        setIsProcessing(false);
      } catch (err) {
        console.error('OAuth callback error:', err);
        setError(err instanceof Error ? err.message : 'An unexpected error occurred');
        setIsProcessing(false);
      }
    };

    handleCallback();
  }, [searchParams, router]);

  // Show loading state while processing
  if (isProcessing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Completing sign in...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 text-center">
          <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-6 h-6 text-red-600 dark:text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Sign In Failed
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">{error}</p>
          <button
            onClick={() => router.push('/login')}
            className="w-full px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return null;
}

// Loading fallback component
function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <p className="text-gray-600 dark:text-gray-400">Loading...</p>
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <OAuthCallbackContent />
    </Suspense>
  );
}
