import { doc, updateDoc } from "firebase/firestore";
import { getDb } from "./firebase";

/** Returns the current UTC date as "YYYY-MM-DD". */
export function getUtcDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Returns true if lastResetDate is before today (UTC). */
export function needsReset(lastResetDate: string): boolean {
  return lastResetDate < getUtcDateString();
}

/** Resets token balance and updates last_reset_date in Firestore. */
export async function resetTokens(email: string, dailyLimit: number = 100): Promise<void> {
  await updateDoc(doc(getDb(), "waitlist", email), {
    token_balance: dailyLimit,
    last_reset_date: getUtcDateString(),
  });
}

/** Formats token balance for display, clamping to min 0. */
export function formatTokenDisplay(balance: number, dailyLimit: number = 100): string {
  return `Tokens: ${Math.max(0, balance)} / ${dailyLimit}`;
}
