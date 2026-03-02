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

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthIdToken() || getEmbedToken();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(url, { ...options, headers });
}
