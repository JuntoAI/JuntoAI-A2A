import { initializeApp, getApps } from "firebase/app";
import { getFirestore, type Firestore } from "firebase/firestore";

let _db: Firestore | null = null;

function initFirebase(): Firestore {
  if (_db) return _db;

  const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };

  // Validate all required env vars at init time
  for (const [key, value] of Object.entries(firebaseConfig)) {
    if (!value) throw new Error(`Missing Firebase env var: ${key}`);
  }

  // Singleton pattern: only initialize if no app exists
  const app =
    getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];

  _db = getFirestore(app);
  return _db;
}

/** Lazy-initialized Firestore singleton. Only validates env vars on first access. */
export const db: Firestore = new Proxy({} as Firestore, {
  get(_target, prop, receiver) {
    const instance = initFirebase();
    return Reflect.get(instance, prop, receiver);
  },
});
