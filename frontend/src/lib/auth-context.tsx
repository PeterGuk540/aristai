'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import {
  AuthUser,
  getCurrentUser,
  getAccessToken as getToken,
  signOut as cognitoSignOut,
  isAuthenticated as checkAuth,
} from './cognito-auth';
import {
  isGoogleAuthenticated,
  getGoogleUserInfo,
  getGoogleAccessToken,
  clearGoogleTokens,
} from './google-auth';
import {
  isMicrosoftAuthenticated,
  getMicrosoftUserInfo,
  getMicrosoftIdToken,
  clearMicrosoftTokens,
} from './ms-auth';

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signOut: () => void;
  refreshUser: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      // Priority: Check Google tokens first (as per notebook requirements)
      if (isGoogleAuthenticated()) {
        const googleUser = getGoogleUserInfo();
        if (googleUser) {
          setUser({
            email: googleUser.email,
            name: googleUser.name,
            sub: googleUser.sub,
            emailVerified: googleUser.emailVerified,
          });
          setIsAuthenticated(true);
          return;
        }
      }

      // Then check Microsoft tokens
      if (isMicrosoftAuthenticated()) {
        const msUser = getMicrosoftUserInfo();
        if (msUser) {
          setUser({
            email: msUser.email,
            name: msUser.name,
            sub: msUser.sub,
            emailVerified: msUser.emailVerified,
          });
          setIsAuthenticated(true);
          return;
        }
      }

      // Finally check Cognito SDK tokens
      const authenticated = await checkAuth();
      if (authenticated) {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch {
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      await refreshUser();
      setIsLoading(false);
    };
    init();
  }, [refreshUser]);

  const signOut = useCallback(() => {
    // Clear all auth tokens (Google, Microsoft, and Cognito)
    clearGoogleTokens();
    clearMicrosoftTokens();
    cognitoSignOut();
    setUser(null);
    setIsAuthenticated(false);
    window.location.href = '/login';
  }, []);

  const getAccessToken = useCallback(async () => {
    // Priority: Check Google token first
    const googleToken = getGoogleAccessToken();
    if (googleToken) {
      return googleToken;
    }
    // Fall back to Cognito SDK token
    return await getToken();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        signOut,
        refreshUser,
        getAccessToken,
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
