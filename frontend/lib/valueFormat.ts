/**
 * Format a proposed_price value based on the scenario's value_format.
 */

export type ValueFormat = "currency" | "time_from_22" | "percent" | "number";

function minutesFrom22ToTime(minutes: number): string {
  // minutes from 10 PM (22:00). 0 = 10:00 PM, 60 = 11:00 PM, 120 = 12:00 AM
  const totalMinutes = 22 * 60 + Math.round(minutes);
  const hours24 = Math.floor(totalMinutes / 60) % 24;
  const mins = totalMinutes % 60;
  // 0-11 in 24h = AM, 12-23 in 24h = PM
  const period = hours24 >= 12 ? "PM" : "AM";
  const hours12 = hours24 === 0 ? 12 : hours24 > 12 ? hours24 - 12 : hours24;
  return `${hours12}:${mins.toString().padStart(2, "0")} ${period}`;
}

export function formatValue(
  value: number | null | undefined,
  format: ValueFormat = "currency",
): string {
  const v = value ?? 0;
  switch (format) {
    case "currency":
      return `€${v.toLocaleString("en-US")}`;
    case "time_from_22":
      return minutesFrom22ToTime(v);
    case "percent":
      return `${Math.round(v)}%`;
    case "number":
      return v.toLocaleString("en-US");
  }
}
