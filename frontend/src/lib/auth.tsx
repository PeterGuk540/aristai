'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Cognito configuration
const COGNITO_DOMAIN = 'aristai-968632-ldr6sk.auth.us-east-1.amazoncognito.com';
const CLIENT_ID = '4sdpd92tsi76oidft1moh3dbht';
const REDIRECT_URI = typeof window !== 'undefined' ? `${window.location.origin}/callback` : '';
const COGNITO_ISSUER = 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_v8JI5l2xO';

interface AuthUser {
  sub: string;
  email: string;
  name?: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  accessToken: string | null;
  idToken: string | null;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);

  useEffect(() => {
    // Check for existing tokens in localStorage
    const storedAccessToken = localStorage.getItem('access_token');
    const storedIdToken = localStorage.getItem('id_token');

    if (storedAccessToken && storedIdToken && !isTokenExpired(storedAccessToken)) {
      setAccessToken(storedAccessToken);
      setIdToken(storedIdToken);
      const payload = parseJwt(storedIdToken);
      if (payload) {
        setUser({
          sub: payload.sub,
          email: payload.email,
          name: payload.name || payload.email,
        });
        setIsAuthenticated(true);
      }
    } else {
      // Clear expired tokens
      localStorage.removeItem('access_token');
      localStorage.removeItem('id_token');
    }
    setIsLoading(false);
  }, []);

  const login = () => {
    const authUrl = `https://${COGNITO_DOMAIN}/login?` +
      `client_id=${CLIENT_ID}` +
      `&response_type=token` +
      `&scope=openid+email+profile` +
      `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}`;
    window.location.href = authUrl;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('id_token');
    setAccessToken(null);
    setIdToken(null);
    setUser(null);
    setIsAuthenticated(false);

    // Redirect to Cognito logout
    const logoutUrl = `https://${COGNITO_DOMAIN}/logout?` +
      `client_id=${CLIENT_ID}` +
      `&logout_uri=${encodeURIComponent(window.location.origin)}`;
    window.location.href = logoutUrl;
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
  return localStorage.getItem('access_token');
}
