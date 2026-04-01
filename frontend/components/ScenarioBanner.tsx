"use client";

const SCENARIOS = [
  "How does my manager react to a salary increase request?",
  "How to convince my parents to let me go to a party tonight?",
  "How to align the whole team on a new product strategy?",
  "How to negotiate a fair remote work policy with HR?",
  "How to find a compromise on the family holiday destination?",
  "How to get buy-in from investors on a pivot?",
  "How to mediate between two co-founders who disagree?",
  "How to renegotiate a freelance contract without losing the client?",
  "How to agree on a fair equity split with a new co-founder?",
  "How to help roommates agree on shared expenses?",
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
