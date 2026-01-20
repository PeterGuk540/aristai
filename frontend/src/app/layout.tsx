import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/Sidebar';
import { UserProvider } from '@/lib/context';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'AristAI - AI-Assisted Classroom Forum',
  description: 'AI-powered platform for synchronous classroom discussions',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <UserProvider>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto bg-gray-50">
              {children}
            </main>
          </div>
        </UserProvider>
      </body>
    </html>
  );
}
