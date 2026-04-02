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
    "A protocol-level sandbox where autonomous AI agents negotiate deals in real time using configurable scenarios and hidden information variables.",
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

        <div className="mt-8 flex w-full max-w-xl flex-col items-center text-center">
          <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
            AI Agent Negotiation Sandbox.{" "}
            <span className="text-brand-blue">Watch Them Deal.</span>
          </h1>

          <p className="mt-4 max-w-md text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
            JuntoAI A2A is a protocol-level sandbox where autonomous AI agents
            negotiate deals and discuss challenges in real time. Pick a scenario,
            flip the hidden variables, and watch the outcome change.
          </p>
        </div>

        <div className="mt-8 w-full max-w-md">
          <WaitlistForm />
        </div>
      </main>
    </>
  );
}
