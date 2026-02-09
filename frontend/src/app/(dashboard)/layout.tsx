'use client';

import { AppShellHandsFree } from '@/components/AppShellHandsFree';
import { AuthProvider } from '@/lib/auth-context';
import { UserProvider } from '@/lib/context';
import { I18nProvider } from '@/lib/i18n-provider';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <UserProvider>
        <I18nProvider>
          <AppShellHandsFree>{children}</AppShellHandsFree>
        </I18nProvider>
      </UserProvider>
    </AuthProvider>
  );
}
