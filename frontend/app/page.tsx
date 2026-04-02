import type { Metadata } from "next";
import WaitlistForm from "@/components/WaitlistForm";
import ScenarioBanner from "@/components/ScenarioBanner";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "JuntoAI A2A Protocol Sandbox",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "A simulation sandbox where autonomous AI agents negotiate real-world scenarios in real time, finding win-win outcomes through transparent reasoning and configurable hidden variables.",
  url: "https://app.juntoai.org",
  author: {
    "@type": "Organization",
    name: "JuntoAI",
    url: "https://juntoai.org",
  },
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "EUR",
    description: "Free access with 100 tokens per day",
  },
};

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <main className="flex min-h-screen flex-col items-center justify-center bg-brand-offwhite px-4 py-16 sm:px-6 lg:px-8">
        <div className="w-screen">
          <ScenarioBanner />
        </div>

        <div className="mt-8 flex w-full max-w-3xl flex-col items-center text-center">
          <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
            AI Negotiation Sandbox.{" "}
            <span className="text-brand-blue">Find the Win‑Win.</span>
          </h1>

          <p className="mt-4 max-w-2xl text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
            Real negotiations aren't about one side winning. They're about
            finding outcomes everyone can live with. JuntoAI A2A simulates that
            process. Autonomous AI agents work through scenarios in real time,
            searching for common ground while protecting their own interests.
          </p>

          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-brand-charcoal/50">
            Pick a scenario, flip the hidden variables, and watch how a single
            piece of information reshapes the entire conversation.
          </p>
        </div>

        <div className="mt-8 w-full max-w-md">
          <WaitlistForm />
        </div>

        {/* Win-win value props */}
        <div className="mt-12 grid w-full max-w-2xl gap-6 sm:grid-cols-3">
          <div className="text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-green/10 text-lg">
              🤝
            </div>
            <p className="mt-2 text-sm font-medium text-brand-charcoal">
              Not zero-sum
            </p>
            <p className="mt-1 text-xs text-brand-charcoal/50">
              Agents seek mutual benefit, not domination. Watch them find
              creative compromises.
            </p>
          </div>
          <div className="text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-blue/10 text-lg">
              🔍
            </div>
            <p className="mt-2 text-sm font-medium text-brand-charcoal">
              Glass box reasoning
            </p>
            <p className="mt-1 text-xs text-brand-charcoal/50">
              See every agent's inner thoughts before they speak. Understand why
              they concede or hold firm.
            </p>
          </div>
          <div className="text-center">
            <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-green/10 text-lg">
              🎛️
            </div>
            <p className="mt-2 text-sm font-medium text-brand-charcoal">
              One toggle changes everything
            </p>
            <p className="mt-1 text-xs text-brand-charcoal/50">
              Give an agent a secret, a competing offer, a hidden deadline, and
              watch the entire dynamic shift.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
