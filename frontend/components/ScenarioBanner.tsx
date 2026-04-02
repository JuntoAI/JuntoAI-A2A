"use client";

const SCENARIOS = [
  "My landlord wants to raise rent 30%. What's a fair counter?",
  "The team can't agree on a product direction before the deadline",
  "I need a raise but my manager keeps dodging the conversation",
  "Two co-founders disagree on equity. The partnership is at risk",
  "How to close a six-figure deal when the client keeps stalling",
  "Our family holiday plan turns into a fight every single year",
  "The investor wants 25% equity for a seed round. Is that fair?",
  "My freelance client wants more scope but won't increase the budget",
  "HR says no to remote work, but half the team is threatening to leave",
  "Roommates can't split expenses without someone feeling ripped off",
];

// Duplicate for seamless infinite scroll
const ITEMS = [...SCENARIOS, ...SCENARIOS];

export default function ScenarioBanner() {
  return (
    <div className="w-full overflow-hidden py-4">
      <div className="animate-scroll flex w-max gap-6">
        {ITEMS.map((text, i) => (
          <span
            key={i}
            className="inline-flex shrink-0 items-center rounded-full border border-brand-blue/20 bg-white px-4 py-2 text-sm text-brand-charcoal/80 shadow-sm"
          >
            <span className="mr-2 text-brand-green">●</span>
            {text}
          </span>
        ))}
      </div>
    </div>
  );
}
