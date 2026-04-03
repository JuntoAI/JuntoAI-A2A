/**
 * Local mode detection helper.
 *
 * NEXT_PUBLIC_RUN_MODE is inlined at build time by Next.js.
 * When the value is anything other than "cloud", the app runs in local mode
 * (auth bypass, no token limits, skip waitlist gate).
 */
export const isLocalMode = process.env.NEXT_PUBLIC_RUN_MODE !== "cloud";
