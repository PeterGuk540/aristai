'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';

function CanvasOAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    const run = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const oauthError = searchParams.get('error');

      if (oauthError) {
        setError(searchParams.get('error_description') || oauthError);
        setIsProcessing(false);
        return;
      }
      if (!code || !state) {
        setError('Missing Canvas OAuth callback parameters.');
        setIsProcessing(false);
        return;
      }

      try {
        const redirectUri =
          sessionStorage.getItem('canvas_oauth_redirect_uri') ||
          `${window.location.origin}/oauth/canvas-callback`;
        await api.exchangeCanvasOAuth({
          code,
          state,
          redirect_uri: redirectUri,
        });
        router.replace('/integrations?canvas_oauth=success');
      } catch (e: any) {
        setError(e?.message || 'Failed to complete Canvas OAuth.');
        setIsProcessing(false);
      }
    };

    void run();
  }, [router, searchParams]);

  if (isProcessing && !error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-stone-300 border-t-stone-700" />
          <p className="mt-3 text-sm text-neutral-600">Completing Canvas connection...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
          <p className="text-lg font-semibold">Canvas connection failed</p>
          <p className="mt-2 text-sm">{error}</p>
          <button
            onClick={() => router.replace('/integrations')}
            className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800"
          >
            Back to Integrations
          </button>
        </div>
      </div>
    );
  }

  return null;
}

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-stone-300 border-t-stone-700" />
        <p className="mt-3 text-sm text-neutral-600">Loading...</p>
      </div>
    </div>
  );
}

export default function CanvasOAuthCallbackPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <CanvasOAuthCallbackContent />
    </Suspense>
  );
}
