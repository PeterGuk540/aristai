'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Cognito configuration - Using friend's Cognito (us-east-2, jjh-user-pool)
const COGNITO_DOMAIN = 'https://jjh-968632-vo9qy8.auth.us-east-2.amazoncognito.com';
const CLIENT_ID = '1rv3c7kkku7vvn8m4nepbmpdeo';
const USER_POOL_ID = 'us-east-2_DEnz6h6Ea';

// Supported Identity Providers
const IDP_COGNITO = 'COGNITO';
const IDP_GOOGLE = 'Google';

interface AuthUser {
  sub: string;
  email: string;
  name?: string;
  picture?: string;
  identityProvider?: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  accessToken: string | null;
  idToken: string | null;
  login: (provider?: 'cognito' | 'google') => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage key prefix (Cognito format)
const STORAGE_KEY = `CognitoIdentityServiceProvider.${CLIENT_ID}`;

function parseJwt(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;
  return Date.now() >= payload.exp * 1000;
}

// Get stored tokens from localStorage
function getStoredTokens(): { accessToken: string | null; idToken: string | null; refreshToken: string | null; username: string | null } {
  if (typeof window === 'undefined') {
    return { accessToken: null, idToken: null, refreshToken: null, username: null };
  }

  const username = localStorage.getItem(`${STORAGE_KEY}.LastAuthUser`);
  if (!username) {
    return { accessToken: null, idToken: null, refreshToken: null, username: null };
  }

  return {
    accessToken: localStorage.getItem(`${STORAGE_KEY}.${username}.accessToken`),
    idToken: localStorage.getItem(`${STORAGE_KEY}.${username}.idToken`),
    refreshToken: localStorage.getItem(`${STORAGE_KEY}.${username}.refreshToken`),
    username,
  };
}

// Store tokens to localStorage
function storeTokens(tokens: { access_token: string; id_token: string; refresh_token?: string }, username: string): void {
  localStorage.setItem(`${STORAGE_KEY}.LastAuthUser`, username);
  localStorage.setItem(`${STORAGE_KEY}.${username}.accessToken`, tokens.access_token);
  localStorage.setItem(`${STORAGE_KEY}.${username}.idToken`, tokens.id_token);
  if (tokens.refresh_token) {
    localStorage.setItem(`${STORAGE_KEY}.${username}.refreshToken`, tokens.refresh_token);
  }
}

// Clear all tokens from localStorage
function clearTokens(): void {
  if (typeof window === 'undefined') return;

  Object.keys(localStorage).forEach(key => {
    if (key.startsWith(STORAGE_KEY)) {
      localStorage.removeItem(key);
    }
  });
}

// Exchange authorization code for tokens
export async function exchangeCodeForToken(code: string, redirectUri: string): Promise<{
  access_token: string;
  id_token: string;
  refresh_token?: string;
}> {
  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: CLIENT_ID,
      code: code,
      redirect_uri: redirectUri.split('?')[0], // Must match exactly
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Token exchange failed: ${error}`);
  }

  return response.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);

  // Check for existing tokens on mount
  useEffect(() => {
    const { accessToken: storedAccessToken, idToken: storedIdToken } = getStoredTokens();

    if (storedAccessToken && storedIdToken && !isTokenExpired(storedAccessToken)) {
      setAccessToken(storedAccessToken);
      setIdToken(storedIdToken);
      const payload = parseJwt(storedIdToken);
      if (payload) {
        setUser({
          sub: payload.sub,
          email: payload.email,
          name: payload.name || payload['cognito:username'] || payload.email,
          picture: payload.picture,
          identityProvider: payload.identities?.[0]?.providerName || 'COGNITO',
        });
        setIsAuthenticated(true);
      }
    } else {
      // Clear expired tokens
      clearTokens();
    }
    setIsLoading(false);
  }, []);

  // Update state after successful token storage
  const updateAuthState = (tokens: { access_token: string; id_token: string }) => {
    setAccessToken(tokens.access_token);
    setIdToken(tokens.id_token);
    const payload = parseJwt(tokens.id_token);
    if (payload) {
      setUser({
        sub: payload.sub,
        email: payload.email,
        name: payload.name || payload['cognito:username'] || payload.email,
        picture: payload.picture,
        identityProvider: payload.identities?.[0]?.providerName || 'COGNITO',
      });
      setIsAuthenticated(true);
    }
  };

  const login = (provider: 'cognito' | 'google' = 'cognito') => {
    const redirectUri = `${window.location.origin}/callback`;

    const params = new URLSearchParams({
      client_id: CLIENT_ID,
      response_type: 'code',
      scope: 'openid email profile',
      redirect_uri: redirectUri,
    });

    // Add identity_provider for Google
    if (provider === 'google') {
      params.set('identity_provider', IDP_GOOGLE);
    }

    window.location.href = `${COGNITO_DOMAIN}/oauth2/authorize?${params.toString()}`;
  };

  const logout = () => {
    clearTokens();
    setAccessToken(null);
    setIdToken(null);
    setUser(null);
    setIsAuthenticated(false);

    // Just redirect to home, don't use Cognito logout to avoid redirect_mismatch
    window.location.href = '/';
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        accessToken,
        idToken,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Export for use in API calls
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  const { accessToken } = getStoredTokens();
  return accessToken;
}

// Export storage functions for callback page
export { storeTokens, parseJwt, STORAGE_KEY, CLIENT_ID };
