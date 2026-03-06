import { getAuthIdToken } from './auth.ts';

/** Extract auth token passed via URL hash fragment from forum embed mode. */
function getEmbedToken(): string | null {
  try {
    const hash = window.location.hash;
    if (!hash) return null;
    const params = new URLSearchParams(hash.slice(1)); // remove leading '#'
    return params.get('auth_token') || null;
  } catch {
    return null;
  }
}

/** Check if we're in embed mode (no Cognito auth needed). */
function isEmbedMode(): boolean {
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get('embed') === 'true';
  } catch {
    return false;
  }
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  // getAuthIdToken() now auto-refreshes tokens that are near expiry
  const token = await getAuthIdToken() || getEmbedToken();

  if (!token && !isEmbedMode()) {
    // No valid token and not in embed mode — session has fully expired
    // Dispatch a custom event so the app can redirect to login
    window.dispatchEvent(new CustomEvent('auth:session-expired'));
  }

  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}
