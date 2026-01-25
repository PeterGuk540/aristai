'use client';

import React, { createContext, useContext, ReactNode, useState, useEffect, useCallback } from 'react';
import { useAuth } from './auth-context';
import { api } from './api';

// User context that fetches role from database
// Role determines what features are available (instructor vs student)

interface DbUser {
  id: number;
  name: string;
  email: string;
  role: string;
  auth_provider?: string;
}

interface UserContextType {
  currentUser: DbUser | null;
  setCurrentUser: (user: DbUser | null) => void;
  users: DbUser[];
  isInstructor: boolean;
  loading: boolean;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [dbUser, setDbUser] = useState<DbUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch user from database by email
  const fetchUserFromDb = useCallback(async (email: string) => {
    try {
      const userData = await api.getUserByEmail(email);
      setDbUser(userData);
    } catch (error) {
      console.error('Failed to fetch user from database:', error);
      // Fallback: create a temporary user object with student role
      setDbUser({
        id: 0,
        name: email.split('@')[0],
        email: email,
        role: 'student',
      });
    }
  }, []);

  const refreshUser = useCallback(async () => {
    if (user?.email) {
      await fetchUserFromDb(user.email);
    }
  }, [user?.email, fetchUserFromDb]);

  // Fetch user from database when auth user changes
  useEffect(() => {
    const loadUser = async () => {
      if (!authLoading && isAuthenticated && user?.email) {
        setLoading(true);
        await fetchUserFromDb(user.email);
        setLoading(false);
      } else if (!authLoading && !isAuthenticated) {
        setDbUser(null);
        setLoading(false);
      }
    };
    loadUser();
  }, [authLoading, isAuthenticated, user?.email, fetchUserFromDb]);

  // Determine if current user is an instructor
  const isInstructor = dbUser?.role === 'instructor';

  return (
    <UserContext.Provider
      value={{
        currentUser: dbUser,
        setCurrentUser: setDbUser,
        users: dbUser ? [dbUser] : [],
        isInstructor,
        loading: authLoading || loading,
        refreshUser,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}
