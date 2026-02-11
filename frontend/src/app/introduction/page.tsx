'use client';

import Link from 'next/link';
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  FileText,
  Mic,
  MessageSquareText,
  Users,
} from 'lucide-react';

const sections = [
  {
    icon: BookOpen,
    title: 'Design courses around decisions',
    body: 'Build case-based courses from your syllabus, then align each session to explicit learning objectives.',
  },
  {
    icon: CalendarDays,
    title: 'Run structured live sessions',
    body: 'Move from preparation to facilitation with clear session plans, timing cues, and shared discussion prompts.',
  },
  {
    icon: MessageSquareText,
    title: 'Capture meaningful discussion',
    body: 'Students contribute in real time, instructors steer direction, and each exchange stays tied to outcomes.',
  },
  {
    icon: Mic,
    title: 'Operate hands-free when needed',
    body: 'Voice actions support navigation and classroom operations without interrupting facilitation flow.',
  },
  {
    icon: FileText,
    title: 'Close the loop with reporting',
    body: 'Post-session summaries and participation signals help faculty review what happened and what to adjust next.',
  },
  {
    icon: Users,
    title: 'Scale consistent teaching practice',
    body: 'Give instructors a shared operating model while preserving individual course style and pedagogical intent.',
  },
];

const steps = [
  'Share your teaching context and outcomes during demo intake.',
  'Walk through your current workflow with our team.',
  'See a guided setup mapped to your classroom model.',
];

export default function PublicIntroductionPage() {
  return (
    <div className="min-h-screen bg-primary text-primary">
      <header className="border-b border-default/80 bg-primary/95 backdrop-blur">
        <div className="container-ebook flex h-16 items-center justify-between">
          <Link href="/introduction" className="text-base font-semibold tracking-tight">
            AristAI
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm text-secondary">
            <a href="#how-it-works" className="link-hover">How It Works</a>
            <a href="#capabilities" className="link-hover">Capabilities</a>
            <a href="#demo" className="link-hover">Request Demo</a>
          </nav>
          <Link href="/login" className="btn-primary-ebook">
            Request a demo
          </Link>
        </div>
      </header>

      <main>
        <section className="container-ebook py-16 lg:py-24">
          <p className="section-label mb-4">Product Introduction</p>
          <h1 className="max-w-4xl text-balance mb-6">
            A teaching platform for live, case-based learning.
          </h1>
          <p className="max-w-3xl text-lg text-secondary mb-8">
            AristAI helps instructors run high-quality discussion sessions with a consistent structure,
            role-aware tools, and practical reporting. Access is provisioned through guided demos.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/login" className="btn-primary-ebook gap-2">
              Request a demo
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#how-it-works" className="btn-secondary-ebook">
              See how it works
            </a>
          </div>
        </section>

        <section id="how-it-works" className="bg-section-alt py-16">
          <div className="container-ebook">
            <p className="section-label mb-3">How It Works</p>
            <h2 className="mb-10">From planning to facilitation to review</h2>
            <div className="grid md:grid-cols-3 gap-6">
              {steps.map((step, index) => (
                <div key={step} className="card-ebook">
                  <div className="mb-4 inline-flex h-8 w-8 items-center justify-center rounded-full bg-yellow text-black text-sm font-semibold">
                    {index + 1}
                  </div>
                  <p className="text-sm text-secondary">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="capabilities" className="container-ebook py-16">
          <p className="section-label mb-3">Capabilities</p>
          <h2 className="mb-10">Built for classroom discussion workflows</h2>
          <div className="grid-3-col">
            {sections.map((section) => (
              <article key={section.title} className="card-ebook card-hover">
                <div className="icon-box mb-4">
                  <section.icon className="text-yellow" />
                </div>
                <h3 className="text-base mb-2">{section.title}</h3>
                <p className="text-sm text-secondary">{section.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="demo" className="bg-section-warm py-16">
          <div className="container-ebook">
            <div className="card-ebook max-w-3xl">
              <p className="section-label mb-3">Access</p>
              <h2 className="mb-4">Request a demo to access the platform</h2>
              <p className="text-secondary mb-6">
                We use a guided onboarding process for institutions and teaching teams. Sign in to submit
                your request and continue to setup.
              </p>
              <ul className="space-y-3 mb-8">
                <li className="flex items-start gap-2 text-sm text-secondary">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-yellow" />
                  Product walkthrough tailored to your teaching context
                </li>
                <li className="flex items-start gap-2 text-sm text-secondary">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-yellow" />
                  Role-specific setup for instructors and learners
                </li>
                <li className="flex items-start gap-2 text-sm text-secondary">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-yellow" />
                  Supported rollout plan for live sessions
                </li>
              </ul>
              <Link href="/login" className="btn-primary-ebook gap-2">
                Continue to request demo
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
