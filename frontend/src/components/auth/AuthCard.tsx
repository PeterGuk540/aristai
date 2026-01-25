'use client';

import { GraduationCap } from 'lucide-react';

interface AuthCardProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

export function AuthCard({ children, title, subtitle }: AuthCardProps) {
  return (
    <div className="min-h-screen flex">
      {/* Left side - Branding (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-600 to-primary-800 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3">
            <GraduationCap className="h-10 w-10 text-white" />
            <span className="text-2xl font-bold text-white">AristAI</span>
          </div>
        </div>
        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            AI-Powered Classroom Forum
          </h1>
          <p className="text-primary-100 text-lg">
            Enhance your teaching and learning experience with intelligent discussion management,
            real-time insights, and AI-assisted interventions.
          </p>
          <div className="flex gap-4 pt-4">
            <div className="bg-white/10 rounded-lg p-4 flex-1">
              <div className="text-3xl font-bold text-white">Smart</div>
              <div className="text-primary-200 text-sm">AI Copilot</div>
            </div>
            <div className="bg-white/10 rounded-lg p-4 flex-1">
              <div className="text-3xl font-bold text-white">Live</div>
              <div className="text-primary-200 text-sm">Sessions</div>
            </div>
            <div className="bg-white/10 rounded-lg p-4 flex-1">
              <div className="text-3xl font-bold text-white">Rich</div>
              <div className="text-primary-200 text-sm">Reports</div>
            </div>
          </div>
        </div>
        <div className="text-primary-200 text-sm">
          &copy; {new Date().getFullYear()} AristAI. All rights reserved.
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-12 bg-gray-50 dark:bg-gray-900">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-2 mb-8">
            <GraduationCap className="h-8 w-8 text-primary-600 dark:text-primary-400" />
            <span className="text-xl font-bold text-gray-900 dark:text-white">AristAI</span>
          </div>

          {/* Card */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h2>
              {subtitle && (
                <p className="mt-2 text-gray-600 dark:text-gray-400">{subtitle}</p>
              )}
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
