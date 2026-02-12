'use client';

import { BookOpen, Calendar, FileText, GraduationCap, MessageSquare } from 'lucide-react';

interface AuthCardProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

const valueCards = [
  {
    icon: BookOpen,
    title: 'Course Design',
    body: 'Structure outcomes, materials, and case prompts with clear teaching intent.',
  },
  {
    icon: Calendar,
    title: 'Session Flow',
    body: 'Run live discussions with reliable status controls and facilitation support.',
  },
  {
    icon: MessageSquare,
    title: 'Discussion Ops',
    body: 'Keep classroom dialogue organized and aligned to learning objectives.',
  },
  {
    icon: FileText,
    title: 'Reporting',
    body: 'Review participation signals and post-class summaries in one workspace.',
  },
];

export function AuthCard({ children, title, subtitle }: AuthCardProps) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-neutral-100 dark:bg-neutral-900">
      <aside className="hidden lg:flex flex-col justify-between border-r border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 px-10 py-9">
        <div className="space-y-9">
          <div className="space-y-5">
            <div className="flex items-center gap-4">
              <img
                src="/EPGUPP_logo_light.png"
                alt="Postgrado Universidad Politecnica"
                className="h-10 object-contain dark:hidden"
              />
              <img
                src="/EPGUPP_logo_white.png"
                alt="Postgrado Universidad Politecnica"
                className="h-10 object-contain hidden dark:block"
              />
              <span className="text-xs font-medium uppercase tracking-[0.14em] text-neutral-500">Academic Partner</span>
            </div>

            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 flex items-center justify-center">
                <GraduationCap className="h-5 w-5 text-neutral-900 dark:text-neutral-100" />
              </div>
              <div>
                <p className="text-lg font-semibold text-neutral-900 dark:text-neutral-100 leading-none">AristAI</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-neutral-500">Teaching Platform</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl font-bold leading-tight text-neutral-900 dark:text-neutral-100 max-w-xl">
              Internal workspace for case-based learning operations.
            </h1>
            <p className="text-base text-neutral-600 dark:text-neutral-400 max-w-xl">
              Designed for instructors and teaching teams who need structured classroom workflows rather than generic AI assistants.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {valueCards.map((card) => (
              <article key={card.title} className="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
                <card.icon className="h-4 w-4 text-neutral-700 dark:text-neutral-300 mb-2" />
                <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{card.title}</h2>
                <p className="mt-1 text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">{card.body}</p>
              </article>
            ))}
          </div>
        </div>

        <p className="text-xs text-neutral-500">&copy; {new Date().getFullYear()} AristAI</p>
      </aside>

      <div className="flex items-center justify-center px-6 py-10 sm:px-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex flex-col items-center gap-4 mb-8">
            <img
              src="/EPGUPP_logo_light.png"
              alt="Postgrado Universidad Politecnica"
              className="h-9 object-contain dark:hidden"
            />
            <img
              src="/EPGUPP_logo_white.png"
              alt="Postgrado Universidad Politecnica"
              className="h-9 object-contain hidden dark:block"
            />
            <div className="flex items-center gap-2">
              <GraduationCap className="h-6 w-6 text-neutral-800 dark:text-neutral-200" />
              <span className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">AristAI</span>
            </div>
          </div>

          <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-md p-8">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">{title}</h2>
              {subtitle && <p className="mt-2 text-neutral-600 dark:text-neutral-400">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
