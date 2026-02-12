'use client';

import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AuthCard, Input, Button, Alert } from '@/components/auth';
import { GoogleLoginButton } from '@/components/GoogleLoginButton';
import { MicrosoftLoginButton } from '@/components/MicrosoftLoginButton';
import { signIn, completeNewPasswordChallenge, completeMfaChallenge, ChallengeResult } from '@/lib/cognito-auth';
import { isAuthenticated } from '@/lib/cognito-auth';
import { isGoogleAuthenticated } from '@/lib/google-auth';
import { isMicrosoftAuthenticated } from '@/lib/ms-auth';

type ViewState = 'login' | 'new-password' | 'mfa';

export default function LoginPage() {
  const router = useRouter();
  const [view, setView] = useState<ViewState>('login');
  const [challenge, setChallenge] = useState<ChallengeResult | null>(null);

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // Validation state
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Check if already authenticated (check Google first, then Microsoft, then Cognito SDK)
  useEffect(() => {
    const checkAuth = async () => {
      // Priority: Check Google tokens first
      if (isGoogleAuthenticated()) {
        router.replace('/courses');
        return;
      }
      // Then check Microsoft tokens
      if (isMicrosoftAuthenticated()) {
        router.replace('/courses');
        return;
      }
      // Finally check Cognito SDK tokens
      const authenticated = await isAuthenticated();
      if (authenticated) {
        router.replace('/courses');
      } else {
        setCheckingAuth(false);
      }
    };
    checkAuth();
  }, [router]);

  const validateEmail = (value: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!value) {
      setEmailError('Email is required');
      return false;
    }
    if (!emailRegex.test(value)) {
      setEmailError('Please enter a valid email address');
      return false;
    }
    setEmailError(null);
    return true;
  };

  const validatePassword = (value: string): boolean => {
    if (!value) {
      setPasswordError('Password is required');
      return false;
    }
    setPasswordError(null);
    return true;
  };

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const isEmailValid = validateEmail(email);
    const isPasswordValid = validatePassword(password);

    if (!isEmailValid || !isPasswordValid) return;

    setLoading(true);

    const result = await signIn(email, password, rememberMe);

    if (result.success) {
      router.replace('/courses');
    } else if ('challenge' in result && result.challenge) {
      setChallenge(result.challenge);
      if (result.challenge.challengeName === 'NEW_PASSWORD_REQUIRED') {
        setView('new-password');
      } else if (
        result.challenge.challengeName === 'SMS_MFA' ||
        result.challenge.challengeName === 'SOFTWARE_TOKEN_MFA'
      ) {
        setView('mfa');
      }
    } else if ('error' in result) {
      setError(result.error);
    }

    setLoading(false);
  };

  const handleNewPassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!challenge?.cognitoUser || !newPassword) return;

    setLoading(true);
    setError(null);

    const result = await completeNewPasswordChallenge(challenge.cognitoUser, newPassword);

    if (result.success) {
      router.replace('/courses');
    } else {
      setError(result.error || 'Failed to set new password');
    }

    setLoading(false);
  };

  const handleMfa = async (e: FormEvent) => {
    e.preventDefault();
    if (!challenge?.cognitoUser || !mfaCode) return;

    setLoading(true);
    setError(null);

    const mfaType = challenge.challengeName === 'SOFTWARE_TOKEN_MFA' ? 'SOFTWARE_TOKEN_MFA' : 'SMS_MFA';
    const result = await completeMfaChallenge(challenge.cognitoUser, mfaCode, mfaType);

    if (result.success) {
      router.replace('/courses');
    } else {
      setError(result.error || 'Invalid verification code');
    }

    setLoading(false);
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-100 dark:bg-neutral-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  // New Password Required view
  if (view === 'new-password') {
    return (
      <AuthCard
        title="Set New Password"
        subtitle="Your account requires a password change"
      >
        <form onSubmit={handleNewPassword} className="space-y-6">
          {error && <Alert type="error" message={error} />}

          <Input
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            showPasswordToggle
            placeholder="Enter new password"
            required
            autoFocus
          />

          <Button type="submit" loading={loading}>
            Set Password
          </Button>
        </form>
      </AuthCard>
    );
  }

  // MFA view
  if (view === 'mfa') {
    return (
      <AuthCard
        title="Verification Required"
        subtitle={
          challenge?.challengeName === 'SMS_MFA'
            ? 'Enter the code sent to your phone'
            : 'Enter the code from your authenticator app'
        }
      >
        <form onSubmit={handleMfa} className="space-y-6">
          {error && <Alert type="error" message={error} />}

          <Input
            label="Verification Code"
            type="text"
            value={mfaCode}
            onChange={(e) => setMfaCode(e.target.value)}
            placeholder="000000"
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            autoFocus
          />

          <Button type="submit" loading={loading}>
            Verify
          </Button>

          <button
            type="button"
            onClick={() => {
              setView('login');
              setChallenge(null);
              setError(null);
            }}
            className="w-full text-sm text-primary-600 hover:text-primary-700 dark:text-primary-400"
          >
            Back to sign in
          </button>
        </form>
      </AuthCard>
    );
  }

  // Main login view
  return (
    <AuthCard
      title="Request demo access"
      subtitle="Sign in to continue with guided onboarding"
    >
      <form onSubmit={handleLogin} className="space-y-6">
        {error && <Alert type="error" message={error} />}
        <Alert
          type="info"
          message="Use your approved account to continue the demo request process."
        />

        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (emailError) validateEmail(e.target.value);
          }}
          error={emailError || undefined}
          placeholder="you@example.com"
          autoComplete="email"
          autoFocus
        />

        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (passwordError) validatePassword(e.target.value);
          }}
          error={passwordError || undefined}
          showPasswordToggle
          placeholder="Enter your password"
          autoComplete="current-password"
        />

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-gray-600 dark:bg-gray-700"
            />
            <span className="text-sm text-gray-600 dark:text-gray-400">Remember me</span>
          </label>
          <Link
            href="/forgot-password"
            className="text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400"
          >
            Forgot password?
          </Link>
        </div>

        <Button type="submit" loading={loading}>
          Sign in
        </Button>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300 dark:border-gray-600" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white dark:bg-gray-800 text-gray-500">or</span>
          </div>
        </div>

        {/* Social Sign-In Buttons */}
        <GoogleLoginButton disabled={loading} />
        <MicrosoftLoginButton disabled={loading} />

        <p className="text-center text-sm text-gray-600 dark:text-gray-400">
          Need onboarding support? Contact your institution admin for access.
        </p>
      </form>
    </AuthCard>
  );
}
