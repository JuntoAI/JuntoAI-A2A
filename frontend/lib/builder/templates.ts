/**
 * Pre-fill templates for the AI Scenario Builder, keyed by persona.
 */
export const BUILDER_TEMPLATES: Record<string, string> = {
  founder: `I'm [Your Name], founder of [Company Name].

Here's my LinkedIn: [Your LinkedIn URL]
Here's my pitch deck: [Pitch Deck Link]

I want to practice pitching to [Target Investor Name].
Their LinkedIn: [Investor LinkedIn URL]
They're a partner at [VC Firm Name]: [VC Firm Link]

My confidence target: [e.g., "Close a $2M seed at $10M pre-money"]`,

  sales: `I'm a [Your Role] at [Company Name].

We sell [Product/Service Description].

I want to practice selling to a [Target Buyer Role].
Typical deal size: [Deal Size, e.g., "$50K ARR"]

Key objections I want to handle:
- [Objection 1, e.g., "Price is too high"]
- [Objection 2, e.g., "We already have a solution"]
- [Objection 3, e.g., "Need to check with my team"]`,
};
