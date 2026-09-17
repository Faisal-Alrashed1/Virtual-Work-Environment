import { useEffect, useLayoutEffect } from "react";

/**
 * useLayoutEffect on the client, useEffect on the server (where
 * useLayoutEffect would otherwise print a console warning, since it
 * does nothing there). Used by ThemeProvider/LocaleProvider to adopt
 * whatever the anti-flash inline script (layout.tsx's <head>) already
 * applied to <html> — synchronously, before the browser paints, so
 * there's no visible flash — without that adoption ever being part of
 * the hydration comparison itself (see the comment on each provider's
 * initial useState for why hydration is the actual constraint here).
 */
export const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;
