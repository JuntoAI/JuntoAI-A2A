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

        <section className="mt-6 flex w-full max-w-md flex-col items-center text-center">
          <a
            href="https://github.com/JuntoAI/JuntoAI-A2A"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Contribute to JuntoAI on GitHub"
            className="inline-flex items-center gap-2 text-sm text-brand-charcoal/70 transition-colors hover:text-brand-blue"
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
            </svg>
            <span>Contribute on GitHub</span>
          </a>
        </section>

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
