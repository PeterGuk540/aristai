'use client';

import { AppShellHandsFree } from '@/components/AppShellHandsFree';
import { AuthProvider } from '@/lib/auth-context';
import { UserProvider } from '@/lib/context';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <UserProvider>
        <AppShellHandsFree>{children}</AppShellHandsFree>
      </UserProvider>
    </AuthProvider>
  );
}
