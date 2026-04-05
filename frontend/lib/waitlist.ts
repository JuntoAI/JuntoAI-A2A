import { doc, getDoc, setDoc, serverTimestamp, Timestamp } from "firebase/firestore";
import { getDb } from "./firebase";
import { getUtcDateString } from "./tokens";

export interface WaitlistDocument {
  email: string;
  signed_up_at: Timestamp;
  token_balance: number;
  last_reset_date: string; // "YYYY-MM-DD"
}

/**
 * Joins the waitlist for the given email.
 * - If the email already exists, returns the existing document (no overwrite).
 * - If new, creates a document with 20 tokens (Tier 1) and today's UTC date.
 */
export async function joinWaitlist(email: string): Promise<WaitlistDocument> {
  const normalized = email.toLowerCase().trim();
  const ref = doc(getDb(), "waitlist", normalized);
  const snap = await getDoc(ref);

  if (snap.exists()) {
    return snap.data() as WaitlistDocument;
  }

  const newDoc: WaitlistDocument = {
    email: normalized,
    signed_up_at: serverTimestamp() as unknown as Timestamp,
    token_balance: 20,
    last_reset_date: getUtcDateString(),
  };

  await setDoc(ref, newDoc);
  return newDoc;
}
