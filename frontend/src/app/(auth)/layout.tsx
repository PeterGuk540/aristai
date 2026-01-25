import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AristAI - Sign In',
  description: 'Sign in to AristAI',
};

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
