'use client';

import React, { createContext, useContext, ReactNode } from 'react';
import { useAuth } from './auth-context';

// Simplified user context - for backward compatibility
// In the new system, user info comes from Cognito auth

interface UserContextType {
  currentUser: { id: number; name: string; email: string; role: string } | null;
  setCurrentUser: (user: any) => void;
  users: any[];
  isInstructor: boolean;
  loading: boolean;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  // Map Cognito user to legacy format
  // For now, we treat all authenticated users as instructors
  // In a real app, you'd check Cognito groups or a database
  const currentUser = user
    ? {
        id: 1,
        name: user.name || user.email.split('@')[0],
        email: user.email,
        role: 'instructor', // Default to instructor for now
      }
    : null;

  return (
    <UserContext.Provider
      value={{
        currentUser,
        setCurrentUser: () => {}, // No-op for compatibility
        users: currentUser ? [currentUser] : [],
        isInstructor: true, // Default to true for now
        loading: isLoading,
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
