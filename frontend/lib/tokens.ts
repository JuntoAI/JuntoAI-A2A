/** Returns the current UTC date as "YYYY-MM-DD". */
export function getUtcDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Formats token balance for display, clamping to min 0. */
export function formatTokenDisplay(balance: number, dailyLimit: number): string {
  return `Tokens: ${Math.max(0, balance)} / ${dailyLimit}`;
}
