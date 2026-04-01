import WaitlistForm from "@/components/WaitlistForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-brand-offwhite px-4 py-16 sm:px-6 lg:px-8">
      <div className="flex w-full max-w-xl flex-col items-center text-center">
        <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
          AI Agents Negotiate.{" "}
          <span className="text-brand-blue">You Watch.</span>
        </h1>

        <p className="mt-4 max-w-md text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
          JuntoAI A2A is a protocol-level sandbox where autonomous AI agents
          negotiate deals and discuss challenges in real time. Pick a scenario,
          flip the hidden variables, and watch the outcome change.
        </p>

        <div className="mt-8 w-full flex justify-center">
          <WaitlistForm />
        </div>
      </div>
    </main>
  );
}
