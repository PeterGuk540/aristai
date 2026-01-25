'use client';

import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AuthCard, Input, Button, Alert, PasswordStrength } from '@/components/auth';
import { forgotPassword, confirmForgotPassword, isAuthenticated } from '@/lib/cognito-auth';

type ViewState = 'request' | 'reset';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [view, setView] = useState<ViewState>('request');

  // Form state
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  // Validation state
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);

  // Check if already authenticated
  useEffect(() => {
    const checkAuth = async () => {
      const authenticated = await isAuthenticated();
      if (authenticated) {
        router.replace('/dashboard');
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
    if (value.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return false;
    }
    setPasswordError(null);
    return true;
  };

  const validateConfirmPassword = (value: string): boolean => {
    if (!value) {
      setConfirmPasswordError('Please confirm your password');
      return false;
    }
    if (value !== newPassword) {
      setConfirmPasswordError('Passwords do not match');
      return false;
    }
    setConfirmPasswordError(null);
    return true;
  };

  const handleRequestCode = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!validateEmail(email)) return;

    setLoading(true);

    const result = await forgotPassword(email);

    if (result.success) {
      setView('reset');
      setSuccess('A verification code has been sent to your email.');
    } else {
      setError(result.error || 'Failed to send reset code');
    }

    setLoading(false);
  };

  const handleResetPassword = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!code) {
      setError('Please enter the verification code');
      return;
    }

    const isPasswordValid = validatePassword(newPassword);
    const isConfirmValid = validateConfirmPassword(confirmPassword);

    if (!isPasswordValid || !isConfirmValid) return;

    setLoading(true);

    const result = await confirmForgotPassword(email, code, newPassword);

    if (result.success) {
      setSuccess('Password reset successful! Redirecting to login...');
      setTimeout(() => {
        router.push('/login');
      }, 1500);
    } else {
      setError(result.error || 'Failed to reset password');
    }

    setLoading(false);
  };

  const handleResendCode = async () => {
    setLoading(true);
    setError(null);

    const result = await forgotPassword(email);

    if (result.success) {
      setSuccess('A new verification code has been sent to your email.');
    } else {
      setError(result.error || 'Failed to resend code');
    }

    setLoading(false);
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  // Reset password view (Step 2)
  if (view === 'reset') {
    return (
      <AuthCard
        title="Reset your password"
        subtitle={`Enter the code sent to ${email}`}
      >
        <form onSubmit={handleResetPassword} className="space-y-6">
          {error && <Alert type="error" message={error} />}
          {success && <Alert type="success" message={success} />}

          <Input
            label="Verification Code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Enter 6-digit code"
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            autoFocus
          />

          <div className="space-y-2">
            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                if (passwordError) validatePassword(e.target.value);
                if (confirmPassword && confirmPasswordError) {
                  validateConfirmPassword(confirmPassword);
                }
              }}
              onBlur={() => validatePassword(newPassword)}
              error={passwordError || undefined}
              showPasswordToggle
              placeholder="Create a new password"
              required
              autoComplete="new-password"
            />
            <PasswordStrength password={newPassword} />
          </div>

          <Input
            label="Confirm New Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (confirmPasswordError) validateConfirmPassword(e.target.value);
            }}
            onBlur={() => validateConfirmPassword(confirmPassword)}
            error={confirmPasswordError || undefined}
            showPasswordToggle
            placeholder="Confirm your new password"
            required
            autoComplete="new-password"
          />

          <Button type="submit" loading={loading}>
            Reset Password
          </Button>

          <div className="text-center space-y-2">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Didn&apos;t receive the code?
            </p>
            <button
              type="button"
              onClick={handleResendCode}
              disabled={loading}
              className="text-sm font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 disabled:opacity-50"
            >
              Resend verification code
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              setView('request');
              setCode('');
              setNewPassword('');
              setConfirmPassword('');
              setError(null);
              setSuccess(null);
            }}
            className="w-full text-sm text-gray-600 hover:text-gray-700 dark:text-gray-400"
          >
            Use a different email
          </button>
        </form>
      </AuthCard>
    );
  }

  // Request code view (Step 1)
  return (
    <AuthCard
      title="Forgot your password?"
      subtitle="Enter your email and we'll send you a reset code"
    >
      <form onSubmit={handleRequestCode} className="space-y-6">
        {error && <Alert type="error" message={error} />}

        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (emailError) validateEmail(e.target.value);
          }}
          onBlur={() => validateEmail(email)}
          error={emailError || undefined}
          placeholder="you@example.com"
          required
          autoComplete="email"
          autoFocus
        />

        <Button type="submit" loading={loading}>
          Send Reset Code
        </Button>

        <p className="text-center text-sm text-gray-600 dark:text-gray-400">
          Remember your password?{' '}
          <Link
            href="/login"
            className="font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400"
          >
            Sign in
          </Link>
        </p>
      </form>
    </AuthCard>
  );
}
