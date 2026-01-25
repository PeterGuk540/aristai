'use client';

import { useState, useEffect, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AuthCard, Input, Button, Alert, PasswordStrength } from '@/components/auth';
import { signUp, confirmSignUp, resendConfirmationCode, isAuthenticated } from '@/lib/cognito-auth';

type ViewState = 'register' | 'verify';

export default function RegisterPage() {
  const router = useRouter();
  const [view, setView] = useState<ViewState>('register');

  // Form state
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');

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
    if (value !== password) {
      setConfirmPasswordError('Passwords do not match');
      return false;
    }
    setConfirmPasswordError(null);
    return true;
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const isEmailValid = validateEmail(email);
    const isPasswordValid = validatePassword(password);
    const isConfirmValid = validateConfirmPassword(confirmPassword);

    if (!isEmailValid || !isPasswordValid || !isConfirmValid) return;

    setLoading(true);

    const result = await signUp(email, password, name || undefined);

    if (result.success) {
      setView('verify');
      setSuccess('We sent a verification code to your email. Please check your inbox.');
    } else {
      setError(result.error || 'Registration failed');
    }

    setLoading(false);
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    if (!verificationCode) {
      setError('Please enter the verification code');
      return;
    }

    setLoading(true);
    setError(null);

    const result = await confirmSignUp(email, verificationCode);

    if (result.success) {
      setSuccess('Email verified! Redirecting to login...');
      setTimeout(() => {
        router.push('/login');
      }, 1500);
    } else {
      setError(result.error || 'Verification failed');
    }

    setLoading(false);
  };

  const handleResendCode = async () => {
    setLoading(true);
    setError(null);

    const result = await resendConfirmationCode(email);

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

  // Verification view
  if (view === 'verify') {
    return (
      <AuthCard
        title="Verify your email"
        subtitle={`Enter the code sent to ${email}`}
      >
        <form onSubmit={handleVerify} className="space-y-6">
          {error && <Alert type="error" message={error} />}
          {success && <Alert type="success" message={success} />}

          <Input
            label="Verification Code"
            type="text"
            value={verificationCode}
            onChange={(e) => setVerificationCode(e.target.value)}
            placeholder="Enter 6-digit code"
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            autoFocus
          />

          <Button type="submit" loading={loading}>
            Verify Email
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
              setView('register');
              setError(null);
              setSuccess(null);
            }}
            className="w-full text-sm text-gray-600 hover:text-gray-700 dark:text-gray-400"
          >
            Back to registration
          </button>
        </form>
      </AuthCard>
    );
  }

  // Main registration view
  return (
    <AuthCard
      title="Create your account"
      subtitle="Get started with AristAI"
    >
      <form onSubmit={handleRegister} className="space-y-6">
        {error && <Alert type="error" message={error} />}

        <Alert
          type="info"
          message="We will send a verification code to your email after registration."
        />

        <Input
          label="Full Name (optional)"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="John Doe"
          autoComplete="name"
        />

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
        />

        <div className="space-y-2">
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (passwordError) validatePassword(e.target.value);
              if (confirmPassword && confirmPasswordError) {
                validateConfirmPassword(confirmPassword);
              }
            }}
            onBlur={() => validatePassword(password)}
            error={passwordError || undefined}
            showPasswordToggle
            placeholder="Create a strong password"
            required
            autoComplete="new-password"
          />
          <PasswordStrength password={password} />
        </div>

        <Input
          label="Confirm Password"
          type="password"
          value={confirmPassword}
          onChange={(e) => {
            setConfirmPassword(e.target.value);
            if (confirmPasswordError) validateConfirmPassword(e.target.value);
          }}
          onBlur={() => validateConfirmPassword(confirmPassword)}
          error={confirmPasswordError || undefined}
          showPasswordToggle
          placeholder="Confirm your password"
          required
          autoComplete="new-password"
        />

        <Button type="submit" loading={loading}>
          Create account
        </Button>

        <p className="text-center text-sm text-gray-600 dark:text-gray-400">
          Already have an account?{' '}
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
