'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.push('/courses');
  }, [router]);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-gray-500">Redirecting to courses...</div>
    </div>
  );
}
