'use client';

import { useCallback, useEffect, useState } from 'react';

const COURSE_KEY = 'aristai:selected-course-id';
const SESSION_KEY = 'aristai:selected-session-id';
const SYNC_EVENT = 'aristai:shared-selection-updated';

function parseStoredInt(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function useSharedCourseSessionSelection() {
  const [selectedCourseId, setSelectedCourseIdState] = useState<number | null>(() => {
    if (typeof window === 'undefined') return null;
    return parseStoredInt(window.localStorage.getItem(COURSE_KEY));
  });
  const [selectedSessionId, setSelectedSessionIdState] = useState<number | null>(() => {
    if (typeof window === 'undefined') return null;
    return parseStoredInt(window.localStorage.getItem(SESSION_KEY));
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const syncFromStorage = () => {
      setSelectedCourseIdState(parseStoredInt(window.localStorage.getItem(COURSE_KEY)));
      setSelectedSessionIdState(parseStoredInt(window.localStorage.getItem(SESSION_KEY)));
    };

    const onStorage = (event: StorageEvent) => {
      if (event.key === COURSE_KEY || event.key === SESSION_KEY) {
        syncFromStorage();
      }
    };

    window.addEventListener('storage', onStorage);
    window.addEventListener(SYNC_EVENT, syncFromStorage as EventListener);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(SYNC_EVENT, syncFromStorage as EventListener);
    };
  }, []);

  const setSelectedCourseId = useCallback((value: number | null) => {
    setSelectedCourseIdState(value);
    if (typeof window === 'undefined') return;

    if (value == null) {
      window.localStorage.removeItem(COURSE_KEY);
    } else {
      window.localStorage.setItem(COURSE_KEY, String(value));
    }
    window.dispatchEvent(new Event(SYNC_EVENT));
  }, []);

  const setSelectedSessionId = useCallback((value: number | null) => {
    setSelectedSessionIdState(value);
    if (typeof window === 'undefined') return;

    if (value == null) {
      window.localStorage.removeItem(SESSION_KEY);
    } else {
      window.localStorage.setItem(SESSION_KEY, String(value));
    }
    window.dispatchEvent(new Event(SYNC_EVENT));
  }, []);

  return {
    selectedCourseId,
    setSelectedCourseId,
    selectedSessionId,
    setSelectedSessionId,
  };
}
