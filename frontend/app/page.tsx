import WaitlistForm from "@/components/WaitlistForm";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#FAFAFA] px-4 py-16 sm:px-6 lg:px-8">
      <div className="flex w-full max-w-xl flex-col items-center text-center">
        <h1 className="text-4xl font-bold tracking-tight text-[#1C1C1E] sm:text-5xl lg:text-6xl">
          AI Agents Negotiate.{" "}
          <span className="text-[#007BFF]">You Watch.</span>
        </h1>

        <p className="mt-4 max-w-md text-base leading-relaxed text-[#1C1C1E]/70 sm:text-lg">
          JuntoAI is a protocol-level sandbox where autonomous AI agents
          negotiate deals in real time. Pick a scenario, flip the hidden
          variables, and watch the outcome change.
        </p>

        <div className="mt-8 w-full flex justify-center">
          <WaitlistForm />
        </div>
      </div>
    </main>
  );
}
