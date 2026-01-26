'use client';

import React, { createContext, useContext, ReactNode, useState, useEffect, useCallback } from 'react';
import { useAuth } from './auth-context';
import { isGoogleAuthenticated } from './google-auth';
import { isMicrosoftAuthenticated } from './ms-auth';
import { api } from './api';

// User context that fetches role from database
// Role determines what features are available (instructor vs student)

interface DbUser {
  id: number;
  name: string;
  email: string;
  role: string;
  auth_provider?: string;
  instructor_request_status?: 'none' | 'pending' | 'approved' | 'rejected';
  instructor_request_date?: string;
  is_admin?: boolean;
}

interface UserContextType {
  currentUser: DbUser | null;
  setCurrentUser: (user: DbUser | null) => void;
  users: DbUser[];
  isInstructor: boolean;
  isAdmin: boolean;
  hasEnrollments: boolean;
  loading: boolean;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [dbUser, setDbUser] = useState<DbUser | null>(null);
  const [hasEnrollments, setHasEnrollments] = useState(false);
  const [loading, setLoading] = useState(true);

  // Determine auth provider based on how user logged in
  const getAuthProvider = useCallback((): 'cognito' | 'google' | 'microsoft' => {
    if (isGoogleAuthenticated()) return 'google';
    if (isMicrosoftAuthenticated()) return 'microsoft';
    return 'cognito';
  }, []);

  // Fetch user from database by email and auth provider
  // Users are uniquely identified by (email, auth_provider) combination
  // This allows separate accounts for the same email with different auth methods
  const fetchUserFromDb = useCallback(async (email: string, authProvider: 'cognito' | 'google' | 'microsoft') => {
    try {
      const userData = await api.getUserByEmail(email, authProvider);
      setDbUser(userData);

      // Check if user has any enrollments (only for students)
      if (userData.role !== 'instructor' && userData.id) {
        try {
          const enrollments = await api.getUserEnrolledCourses(userData.id);
          setHasEnrollments(enrollments.length > 0);
        } catch {
          setHasEnrollments(false);
        }
      } else {
        // Instructors always have access
        setHasEnrollments(true);
      }
    } catch (error) {
      console.error('Failed to fetch user from database:', error);
      // Fallback: create a temporary user object with student role
      setDbUser({
        id: 0,
        name: email.split('@')[0],
        email: email,
        role: 'student',
        auth_provider: authProvider,
      });
      setHasEnrollments(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    if (user?.email) {
      const authProvider = getAuthProvider();
      await fetchUserFromDb(user.email, authProvider);
    }
  }, [user?.email, fetchUserFromDb, getAuthProvider]);

  // Fetch user from database when auth user changes
  useEffect(() => {
    const loadUser = async () => {
      if (!authLoading && isAuthenticated && user?.email) {
        setLoading(true);
        const authProvider = getAuthProvider();
        await fetchUserFromDb(user.email, authProvider);
        setLoading(false);
      } else if (!authLoading && !isAuthenticated) {
        setDbUser(null);
        setLoading(false);
      }
    };
    loadUser();
  }, [authLoading, isAuthenticated, user?.email, fetchUserFromDb, getAuthProvider]);

  // Determine if current user is an instructor
  const isInstructor = dbUser?.role === 'instructor';
  const isAdmin = dbUser?.is_admin === true;

  return (
    <UserContext.Provider
      value={{
        currentUser: dbUser,
        setCurrentUser: setDbUser,
        users: dbUser ? [dbUser] : [],
        isInstructor,
        isAdmin,
        hasEnrollments,
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
