'use client';

import { AppShell } from '@/components/AppShell';
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
        <AppShell>{children}</AppShell>
      </UserProvider>
    </AuthProvider>
  );
}
