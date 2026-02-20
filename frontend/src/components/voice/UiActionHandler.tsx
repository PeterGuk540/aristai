'use client';

import { useEffect, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';

/**
 * Simple toast helper that logs and shows alert for important messages
 */
const showToast = (message: string, type: 'info' | 'success' | 'error' | 'warning' = 'info') => {
  console.log(`🎤 [${type.toUpperCase()}] ${message}`);
  // For voice feedback, we rely on ElevenLabs TTS, so just log here
};

/**
 * UiActionHandler - Listens for voice-triggered UI actions and handles them
 *
 * Handles ui.openModal events by navigating to appropriate pages/tabs
 * Handles ui.toast events by showing toast notifications
 */
export const UiActionHandler = () => {
  const router = useRouter();
  const pathname = usePathname();

  // Handle modal open events from voice actions
  const handleOpenModal = useCallback((event: CustomEvent) => {
    // Support both 'modalType' and 'modal' field names for flexibility
    const { modalType, modal, ...data } = event.detail || {};
    const effectiveModalType = modalType || modal;

    console.log('🎤 UiActionHandler: openModal event', { modalType: effectiveModalType, data });

    switch (effectiveModalType) {
      // Course actions
      case 'createCourse':
        // Navigate to courses page with create tab selected
        if (pathname !== '/courses') {
          router.push('/courses?tab=create');
        } else {
          // Already on courses page, trigger tab switch
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'create' } }));
        }
        showToast('Opening course creation form...', 'info');
        break;

      case 'selectCourse':
        // Navigate to courses page
        if (pathname !== '/courses') {
          router.push('/courses');
        }
        if (data?.courseName) {
          showToast(`Looking for course: ${data.courseName}`, 'info');
        }
        break;

      case 'manageEnrollments':
        // Navigate to courses page with enrollment tab
        if (pathname !== '/courses') {
          router.push('/courses?tab=enrollment');
        } else {
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'enrollment' } }));
        }
        showToast('Opening enrollment management...', 'info');
        break;

      case 'postCase':
        // Navigate to forum for case study creation
        if (pathname !== '/forum') {
          router.push('/forum');
        }
        showToast('Opening case study creation...', 'info');
        break;

      // Session actions
      case 'createSession':
        // Navigate to sessions page with create tab selected
        if (pathname !== '/sessions') {
          router.push('/sessions?tab=create');
        } else {
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'create' } }));
        }
        showToast('Opening session creation form...', 'info');
        break;

      case 'selectSession':
        // Navigate to sessions page
        if (pathname !== '/sessions') {
          router.push('/sessions');
        }
        if (data?.sessionName) {
          showToast(`Looking for session: ${data.sessionName}`, 'info');
        }
        break;

      case 'goLive':
        // Navigate to sessions page with manage tab
        if (pathname !== '/sessions') {
          router.push('/sessions?tab=manage');
        } else {
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'manage' } }));
        }
        showToast('Ready to go live!', 'success');
        break;

      case 'endSession':
        // Navigate to sessions page with manage tab
        if (pathname !== '/sessions') {
          router.push('/sessions?tab=manage');
        } else {
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'manage' } }));
        }
        showToast('Opening session controls...', 'info');
        break;

      case 'viewMaterials':
        // Navigate to sessions page with materials tab
        if (pathname !== '/sessions') {
          router.push('/sessions?tab=materials');
        } else {
          window.dispatchEvent(new CustomEvent('voice-select-tab', { detail: { tab: 'materials' } }));
        }
        showToast('Opening course materials...', 'info');
        break;

      // Forum actions
      case 'postCase':
      case 'createPost':
        // Navigate to forum page
        if (pathname !== '/forum') {
          router.push('/forum?action=create');
        }
        showToast('Opening new post form...', 'info');
        break;

      case 'viewPosts':
        // Navigate to forum page
        if (pathname !== '/forum') {
          router.push('/forum');
        }
        break;

      // Console actions
      case 'createPoll':
        // Navigate to console page
        if (pathname !== '/console') {
          router.push('/console?action=poll');
        }
        showToast('Opening poll creation...', 'info');
        break;

      case 'startCopilot':
        // Navigate to console page
        if (pathname !== '/console') {
          router.push('/console');
        }
        showToast('Starting AI copilot...', 'success');
        break;

      case 'stopCopilot':
        // Navigate to console page
        if (pathname !== '/console') {
          router.push('/console');
        }
        showToast('Stopping AI copilot...', 'info');
        break;

      // Report actions
      case 'generateReport':
        // Navigate to reports page
        if (pathname !== '/reports') {
          router.push('/reports');
        }
        showToast('Opening report generation...', 'info');
        break;

      default:
        console.log('🎤 UiActionHandler: Unknown modal type', effectiveModalType);
    }
  }, [pathname, router]);

  // Handle toast events from voice actions
  const handleToast = useCallback((event: CustomEvent) => {
    const { message, type = 'info' } = event.detail || {};

    if (!message) return;

    showToast(message, type);
  }, []);

  // Store handlers in refs to prevent event listener duplication
  const handleOpenModalRef = useRef(handleOpenModal);
  const handleToastRef = useRef(handleToast);

  // Keep refs updated with latest handlers
  handleOpenModalRef.current = handleOpenModal;
  handleToastRef.current = handleToast;

  useEffect(() => {
    // Create stable wrapper functions that delegate to refs
    const stableOpenModalHandler = (event: Event) => {
      handleOpenModalRef.current(event as CustomEvent);
    };
    const stableToastHandler = (event: Event) => {
      handleToastRef.current(event as CustomEvent);
    };

    // Listen for UI action events - only added once
    window.addEventListener('ui.openModal', stableOpenModalHandler);
    window.addEventListener('ui.toast', stableToastHandler);

    return () => {
      window.removeEventListener('ui.openModal', stableOpenModalHandler);
      window.removeEventListener('ui.toast', stableToastHandler);
    };
  }, []); // Empty dependency - listeners added only once

  return null;
};

export default UiActionHandler;
