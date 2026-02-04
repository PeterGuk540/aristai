/**
 * Worklet interceptor for ElevenLabs SDK.
 * 
 * This module patches the AudioWorklet.addModule method to intercept
 * attempts to load external worklet files and redirect them to local vendor files.
 */

export function setupWorkletInterceptor() {
  if (typeof window === 'undefined' || typeof AudioWorklet === 'undefined') {
    return; // Not in browser or AudioWorklet not supported
  }

  // Store original addModule method
  const originalAddModule = AudioWorkletNode.prototype.context?.audioWorklet?.addModule;
  
  if (!originalAddModule) {
    console.warn('AudioWorklet.addModule not available for interception');
    return;
  }

  // Override addModule to intercept worklet loading
  AudioWorkletNode.prototype.context.audioWorklet.addModule = async function(moduleURL: string) {
    console.log('🎧 Worklet load requested:', moduleURL);

    // Check if this is an external worklet that should be served locally
    if (moduleURL.includes('libsamplerate.worklet.js') || moduleURL.includes('elevenlabs')) {
      // Redirect to local vendor path
      const localURL = '/vendor/libsamplerate.worklet.js';
      console.log('🔄 Redirecting worklet to local path:', localURL);
      
      try {
        return await originalAddModule.call(this, localURL);
      } catch (error) {
        console.error('❌ Failed to load local worklet:', error);
        // Fallback to original URL
        return await originalAddModule.call(this, moduleURL);
      }
    }

    // For other worklets, use original method
    return await originalAddModule.call(this, moduleURL);
  };

  console.log('✅ Worklet interceptor installed');
}

// Also patch fetch to intercept any CDN requests for worklets
export function setupFetchInterceptor() {
  if (typeof window === 'undefined' || !window.fetch) {
    return;
  }

  const originalFetch = window.fetch;

  window.fetch = async function(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const url = typeof input === 'string' ? input : input.toString();
    
    // Intercept worklet requests
    if (url.includes('libsamplerate.worklet.js') || url.includes('elevenlabs') && url.includes('.js')) {
      const localURL = '/vendor/libsamplerate.worklet.js';
      console.log('🔄 Intercepting fetch, redirecting to:', localURL);
      
      try {
        return await originalFetch.call(this, localURL, init);
      } catch (error) {
        console.error('❌ Failed to fetch local worklet, falling back to original:', error);
        return await originalFetch.call(this, input, init);
      }
    }

    // For all other requests, use original fetch
    return await originalFetch.call(this, input, init);
  };

  console.log('✅ Fetch interceptor installed');
}

// Install both interceptors
export function installInterceptors() {
  setupWorkletInterceptor();
  setupFetchInterceptor();
}