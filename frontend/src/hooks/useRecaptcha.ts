import { useEffect, useCallback, useRef } from "react";

const SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

/** Load the reCAPTCHA v3 script once, globally. */
let scriptLoaded = false;

function loadScript(siteKey: string): Promise<void> {
  if (scriptLoaded) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://www.google.com/recaptcha/api.js?render=${siteKey}`;
    script.async = true;
    script.onload = () => {
      scriptLoaded = true;
      resolve();
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

/**
 * Hook that provides a function to execute reCAPTCHA v3 and get a token.
 * Returns null if reCAPTCHA is not configured (VITE_RECAPTCHA_SITE_KEY unset).
 */
export function useRecaptcha() {
  const ready = useRef(false);

  useEffect(() => {
    if (!SITE_KEY) return;
    loadScript(SITE_KEY).then(() => {
      ready.current = true;
    });
  }, []);

  const execute = useCallback(
    async (action: string): Promise<string | null> => {
      if (!SITE_KEY) return null;

      // Wait briefly for script if not yet loaded
      if (!ready.current) {
        await loadScript(SITE_KEY);
      }

      try {
        const token: string = await (window as any).grecaptcha.execute(SITE_KEY, { action });
        return token;
      } catch {
        console.warn("reCAPTCHA execution failed");
        return null;
      }
    },
    [],
  );

  return { execute, isConfigured: !!SITE_KEY };
}
