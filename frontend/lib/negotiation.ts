/**
 * Negotiation response handler — wires updateTokenBalance from SessionContext
 * to the backend POST /api/v1/negotiation/start response.
 *
 * The actual API call is implemented in a future spec (a2a-backend-core-sse).
 * This helper is ready to be called once that integration lands.
 */

/**
 * Processes the token balance from a negotiation start response.
 * Calls updateTokenBalance on SessionContext to sync client state
 * with the backend's authoritative tokens_remaining value.
 */
export function handleNegotiationResponse(
  tokensRemaining: number,
  updateTokenBalance: (balance: number) => void
): void {
  updateTokenBalance(tokensRemaining);
}
