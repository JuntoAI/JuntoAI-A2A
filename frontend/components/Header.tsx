"use client";

import Link from "next/link";
import Image from "next/image";
import { Github, ExternalLink, LogOut } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import TokenDisplay from "@/components/TokenDisplay";

export default function Header() {
  const { isAuthenticated, isHydrated, email, logout } = useSession();

  const showAuth = isHydrated && isAuthenticated;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-brand-offwhite">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-2 md:px-6">
        {/* Logo */}
        <Link href="/" className="flex-shrink-0">
          <Image
            src="/a2a-logo-400x200.png"
            alt="JuntoAI logo"
            width={72}
            height={36}
            priority
          />
        </Link>

        {/* Nav links — hidden on small screens, visible on md+ */}
        <nav className="hidden items-center gap-4 md:flex" aria-label="Main navigation">
          <a
            href="https://juntoai.org"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-brand-charcoal hover:text-brand-blue transition-colors"
          >
            JuntoAI
            <ExternalLink className="h-3 w-3" />
          </a>
          <a
            href="https://github.com/JuntoAI/JuntoAI-A2A"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-brand-charcoal hover:text-brand-blue transition-colors"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
        </nav>

        {/* Right side — auth-dependent */}
        <div className="flex items-center gap-2 md:gap-3">
          {/* Compact nav links on mobile */}
          <div className="flex items-center gap-2 md:hidden">
            <a
              href="https://juntoai.org"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="JuntoAI homepage"
              className="text-brand-charcoal hover:text-brand-blue transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
            <a
              href="https://github.com/JuntoAI/JuntoAI-A2A"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub repository"
              className="text-brand-charcoal hover:text-brand-blue transition-colors"
            >
              <Github className="h-4 w-4" />
            </a>
          </div>

          {showAuth ? (
            <>
              <span
                className="hidden truncate max-w-[160px] text-sm text-gray-600 md:inline"
                title={email ?? ""}
              >
                {email}
              </span>
              <TokenDisplay />
              <button
                onClick={logout}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
                aria-label="Logout"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden md:inline">Logout</span>
              </button>
            </>
          ) : (
            <a
              href="#waitlist"
              className="rounded-md bg-brand-blue px-4 py-1.5 text-sm font-medium text-white hover:opacity-90 transition-opacity"
            >
              Join Waitlist
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
