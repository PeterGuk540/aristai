'use client';

import { BookOpen, Calendar, FileText, MessageSquare } from 'lucide-react';

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
    tone: 'bg-sky-50 border-sky-200 dark:bg-sky-950/30 dark:border-sky-900',
    iconTone: 'text-sky-700 dark:text-sky-300',
  },
  {
    icon: Calendar,
    title: 'Session Flow',
    body: 'Run live discussions with reliable status controls and facilitation support.',
    tone: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900',
    iconTone: 'text-emerald-700 dark:text-emerald-300',
  },
  {
    icon: MessageSquare,
    title: 'Discussion Ops',
    body: 'Keep classroom dialogue organized and aligned to learning objectives.',
    tone: 'bg-violet-50 border-violet-200 dark:bg-violet-950/30 dark:border-violet-900',
    iconTone: 'text-violet-700 dark:text-violet-300',
  },
  {
    icon: FileText,
    title: 'Reporting',
    body: 'Review participation signals and post-class summaries in one workspace.',
    tone: 'bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900',
    iconTone: 'text-amber-700 dark:text-amber-300',
  },
];

export function AuthCard({ children, title, subtitle }: AuthCardProps) {
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.08fr_1fr] bg-stone-50 dark:bg-slate-950">
      <aside className="hidden lg:flex flex-col justify-between border-r border-stone-200/70 dark:border-slate-800 bg-[radial-gradient(circle_at_20%_25%,#ffd19f_0%,#ff8a7a_34%,#8f52d7_70%,#5a36b8_100%)] px-10 py-10 text-white">
        <div className="space-y-9">
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-4 rounded-xl border border-white/25 bg-white/10 px-4 py-3 backdrop-blur-sm">
              <img
                src="/EPGUPP_logo_light.png"
                alt="Postgrado Universidad Politecnica"
                className="h-8 object-contain brightness-0 invert"
              />
              <img
                src="/EPGUPP_logo_white.png"
                alt="Postgrado Universidad Politecnica"
                className="h-8 object-contain hidden"
              />
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/80">Academic Partner</span>
            </div>

            <div className="rounded-xl border border-white/25 bg-white/10 p-4 backdrop-blur-sm">
              <img src="/AristAI_logo.png" alt="AristAI" className="h-11 w-auto brightness-0 invert" />
              <p className="mt-2 text-xs uppercase tracking-[0.12em] text-white/75">Teaching Platform</p>
            </div>
          </div>

          <div className="space-y-3">
            <h1 className="text-4xl font-bold leading-tight max-w-xl">
              Internal workspace for case-based learning operations.
            </h1>
            <p className="text-base text-white/85 max-w-xl">
              Structured for instructors and teaching teams who need dependable classroom workflows.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {valueCards.map((card) => (
              <article key={card.title} className="rounded-xl border border-white/15 bg-white/90 p-4 text-slate-900 shadow-sm">
                <card.icon className={`h-4 w-4 mb-2 ${card.iconTone}`} />
                <h2 className="text-sm font-semibold">{card.title}</h2>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">{card.body}</p>
              </article>
            ))}
          </div>
        </div>

        <p className="text-xs text-white/70">&copy; {new Date().getFullYear()} AristAI</p>
      </aside>

      <div className="flex items-center justify-center px-6 py-10 sm:px-12 bg-white dark:bg-slate-950">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex flex-col items-center gap-3 mb-8">
            <img
              src="/EPGUPP_logo_light.png"
              alt="Postgrado Universidad Politecnica"
              className="h-8 object-contain dark:hidden"
            />
            <img
              src="/EPGUPP_logo_white.png"
              alt="Postgrado Universidad Politecnica"
              className="h-8 object-contain hidden dark:block"
            />
            <img src="/AristAI_logo.png" alt="AristAI" className="h-10 w-auto" />
          </div>

          <div className="bg-white dark:bg-slate-900 border border-stone-200 dark:border-slate-800 rounded-xl p-8 shadow-sm">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{title}</h2>
              {subtitle && <p className="mt-2 text-slate-600 dark:text-slate-400">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
