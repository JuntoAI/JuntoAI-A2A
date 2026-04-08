/**
 * Pure function to build notification title/body from deal status and summary.
 * No React/DOM dependencies — independently testable.
 */

export interface NotificationContent {
  title: string;
  body: string;
}

type TerminalDealStatus = "Agreed" | "Blocked" | "Failed";

const TITLE_MAP: Record<TerminalDealStatus, string> = {
  Agreed: "Deal Agreed",
  Blocked: "Deal Blocked",
  Failed: "Negotiation Failed",
};

const FALLBACK_BODY: Record<TerminalDealStatus, string> = {
  Agreed: "Your negotiation reached an agreement.",
  Blocked: "Your negotiation was blocked.",
  Failed: "Negotiation ended without agreement.",
};

export function buildNotificationContent(
  dealStatus: TerminalDealStatus,
  finalSummary: Record<string, unknown>,
): NotificationContent {
  const title = TITLE_MAP[dealStatus];

  let body: string;
  switch (dealStatus) {
    case "Agreed": {
      const offer = finalSummary.current_offer;
      body = offer != null ? `Final offer: ${offer}` : FALLBACK_BODY.Agreed;
      break;
    }
    case "Blocked": {
      const blockedBy = finalSummary.blocked_by;
      body = blockedBy != null ? `Blocked by: ${blockedBy}` : FALLBACK_BODY.Blocked;
      break;
    }
    case "Failed": {
      const reason = finalSummary.reason;
      body = reason != null ? String(reason) : FALLBACK_BODY.Failed;
      break;
    }
  }

  return { title, body };
}
