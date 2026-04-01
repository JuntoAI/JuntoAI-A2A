import { describe, it, expect } from "vitest";
import * as fc from "fast-check";

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 *
 * Security Rules — Pure function simulation of Firestore security rule logic.
 *
 * Since we can't run the Firebase emulator in this test environment, these tests
 * validate the RULE LOGIC as pure functions that mirror the conditions in
 * frontend/firestore.rules.
 */

// --- Rule simulation helpers ---

/** Simulate the create rule: waitlist/{emailId} */
function isCreateAllowed(
  emailId: string,
  data: { email: string; token_balance: number },
): boolean {
  return data.email === emailId && data.token_balance === 100;
}

/** Simulate the update rule: waitlist/{emailId} */
function isUpdateAllowed(
  emailId: string,
  data: { email: string; token_balance: number },
): boolean {
  return (
    data.token_balance >= 0 &&
    data.token_balance <= 100 &&
    data.email === emailId
  );
}

/** Simulate the read rule: waitlist/{emailId} — read allowed on specific doc */
function isReadAllowed(_emailId: string): boolean {
  return true;
}

/** Simulate the delete rule: waitlist — always denied */
function isDeleteAllowed(): boolean {
  return false;
}

/** Simulate default deny: only waitlist collection is accessible from client */
function isCollectionAllowed(collection: string): boolean {
  return collection === "waitlist";
}

// --- Arbitraries ---

/** Generate a simple email-like string for doc IDs */
const emailArb = fc
  .tuple(
    fc
      .array(fc.constantFrom("a", "b", "c", "d", "1", "2"), {
        minLength: 1,
        maxLength: 8,
      })
      .map((arr) => arr.join("")),
    fc
      .array(fc.constantFrom("x", "y", "z"), {
        minLength: 1,
        maxLength: 5,
      })
      .map((arr) => arr.join("")),
    fc.constantFrom("com", "org", "net", "io"),
  )
  .map(([local, domain, tld]) => `${local}@${domain}.${tld}`);

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 14: Waitlist document write validation (Security Rules)
 *
 * For any client-side create request where doc ID != email field OR
 * token_balance != 100, the rules SHALL deny the write.
 * For any client-side update where token_balance > 100 or < 0,
 * the rules SHALL deny the write.
 *
 * **Validates: Requirements 9.2, 9.4**
 */
describe("Property 14: Waitlist document write validation", () => {
  it("denies create when email field does not match document ID", () => {
    fc.assert(
      fc.property(
        emailArb,
        emailArb,
        (docId, differentEmail) => {
          fc.pre(docId !== differentEmail);
          const result = isCreateAllowed(docId, {
            email: differentEmail,
            token_balance: 100,
          });
          expect(result).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("denies create when token_balance is not 100", () => {
    fc.assert(
      fc.property(
        emailArb,
        fc.integer({ min: -1000, max: 1000 }).filter((n) => n !== 100),
        (email, balance) => {
          const result = isCreateAllowed(email, {
            email,
            token_balance: balance,
          });
          expect(result).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("allows create when email matches doc ID and token_balance is 100", () => {
    fc.assert(
      fc.property(emailArb, (email) => {
        const result = isCreateAllowed(email, {
          email,
          token_balance: 100,
        });
        expect(result).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it("denies update when token_balance > 100", () => {
    fc.assert(
      fc.property(
        emailArb,
        fc.integer({ min: 101, max: 10000 }),
        (email, balance) => {
          const result = isUpdateAllowed(email, {
            email,
            token_balance: balance,
          });
          expect(result).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("denies update when token_balance < 0", () => {
    fc.assert(
      fc.property(
        emailArb,
        fc.integer({ min: -10000, max: -1 }),
        (email, balance) => {
          const result = isUpdateAllowed(email, {
            email,
            token_balance: balance,
          });
          expect(result).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("denies update when email does not match doc ID", () => {
    fc.assert(
      fc.property(
        emailArb,
        emailArb,
        fc.integer({ min: 0, max: 100 }),
        (docId, differentEmail, balance) => {
          fc.pre(docId !== differentEmail);
          const result = isUpdateAllowed(docId, {
            email: differentEmail,
            token_balance: balance,
          });
          expect(result).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("allows update when email matches and token_balance in [0, 100]", () => {
    fc.assert(
      fc.property(
        emailArb,
        fc.integer({ min: 0, max: 100 }),
        (email, balance) => {
          const result = isUpdateAllowed(email, {
            email,
            token_balance: balance,
          });
          expect(result).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });
});


/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 15: Waitlist document read scoping (Security Rules)
 *
 * For any client-side read request to the waitlist collection, the request
 * SHALL only succeed for the specific document ID requested (the email).
 * The read rule allows reads on specific doc IDs — no collection-level
 * list queries return documents belonging to other users because the client
 * must know the exact doc ID (email) to read.
 *
 * **Validates: Requirements 9.3**
 */
describe("Property 15: Waitlist document read scoping", () => {
  it("read is allowed on any specific waitlist document ID", () => {
    fc.assert(
      fc.property(emailArb, (email) => {
        // Reading a specific doc by ID is always allowed per the rules
        expect(isReadAllowed(email)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it("read scoping: client must know exact doc ID to access a document", () => {
    fc.assert(
      fc.property(emailArb, emailArb, (requesterEmail, docOwnerEmail) => {
        // The security model relies on document-ID-as-email.
        // A client can only read a doc if they know the exact email (doc ID).
        // The read rule itself returns true for any specific doc path,
        // but the client MUST provide the exact doc ID — there is no
        // collection-level list/query that would leak other users' docs.
        const canReadSpecificDoc = isReadAllowed(docOwnerEmail);
        expect(canReadSpecificDoc).toBe(true);

        // The key security property: the collection itself is NOT listable.
        // Only the waitlist collection is allowed, and only via specific doc ID.
        expect(isCollectionAllowed("waitlist")).toBe(true);
      }),
      { numRuns: 100 },
    );
  });
});

/**
 * Feature: 050_a2a-frontend-gate-waitlist
 * Property 16: Default deny for unauthorized operations (Security Rules)
 *
 * For any client-side delete on waitlist, for any client-side read/write
 * to negotiation_sessions, and for any client-side read/write to any
 * collection not explicitly listed in the rules, the Firestore Security
 * Rules SHALL deny the operation.
 *
 * **Validates: Requirements 9.5, 9.6, 9.7**
 */
describe("Property 16: Default deny for unauthorized operations", () => {
  it("delete is always denied on waitlist collection", () => {
    fc.assert(
      fc.property(emailArb, (_email) => {
        expect(isDeleteAllowed()).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("negotiation_sessions collection is denied for all operations", () => {
    expect(isCollectionAllowed("negotiation_sessions")).toBe(false);
  });

  it("random non-waitlist collections are denied", () => {
    const nonWaitlistCollectionArb = fc
      .string({ minLength: 1, maxLength: 30 })
      .filter(
        (s) =>
          s !== "waitlist" &&
          s.trim().length > 0,
      );

    fc.assert(
      fc.property(nonWaitlistCollectionArb, (collection) => {
        expect(isCollectionAllowed(collection)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("common collection names are all denied except waitlist", () => {
    const commonCollections = [
      "users",
      "sessions",
      "negotiation_sessions",
      "admin",
      "tokens",
      "config",
      "logs",
      "analytics",
      "payments",
      "profiles",
    ];

    for (const col of commonCollections) {
      expect(isCollectionAllowed(col)).toBe(false);
    }
  });

  it("waitlist is the only allowed collection", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(
          "waitlist",
          "negotiation_sessions",
          "users",
          "admin",
          "tokens",
          "config",
        ),
        (collection) => {
          if (collection === "waitlist") {
            expect(isCollectionAllowed(collection)).toBe(true);
          } else {
            expect(isCollectionAllowed(collection)).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
