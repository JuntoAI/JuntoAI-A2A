"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { Github, ExternalLink, LogOut } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import TokenDisplay from "@/components/TokenDisplay";

export default function Header() {
  const { isAuthenticated, isHydrated, email, logout } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [adminLoggingOut, setAdminLoggingOut] = useState(false);

  const showAuth = isHydrated && isAuthenticated;
  const isLanding = pathname === "/";
  const isAdmin = pathname.startsWith("/admin") && !pathname.startsWith("/admin/login");
  const showNavLinks = pathname === "/" || pathname === "/open-source";
  const isOpenSource = pathname === "/open-source";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-brand-offwhite">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-2 md:px-6">
        {/* Logo + product name — links to arena when authenticated, landing otherwise */}
        <Link href={showAuth ? "/arena" : "/"} className="flex items-center gap-2 flex-shrink-0">
          <Image
            src="/juntoai_logo_500x500.png"
            alt="JuntoAI logo"
            width={32}
            height={32}
            priority
          />
          <span className="text-base font-semibold text-brand-charcoal">
            JuntoAI A2A
          </span>
        </Link>

        {/* Nav links — only on landing page */}
        {showNavLinks && (
          <nav className="hidden items-center gap-4 md:flex" aria-label="Main navigation">
            {!isOpenSource && (
              <Link
                href="/open-source"
                className="text-sm text-brand-charcoal hover:text-brand-blue transition-colors"
              >
                Open Source
              </Link>
            )}
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
        )}

        {/* Right side — auth-dependent */}
        <div className="flex items-center gap-2 md:gap-3">
          {/* Compact nav links on mobile — only on landing page */}
          {showNavLinks && (
            <div className="flex items-center gap-2 md:hidden">
              {!isOpenSource && (
                <Link
                  href="/open-source"
                  className="text-sm text-brand-charcoal hover:text-brand-blue transition-colors"
                >
                  Open Source
                </Link>
              )}
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
          )}

          {showAuth && (
            <>
              <Link
                href="/profile"
                className="hidden truncate max-w-[160px] text-sm text-gray-600 hover:text-brand-blue hover:underline transition-colors md:inline"
                title={email ?? ""}
              >
                {email}
              </Link>
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
          )}

          {isAdmin && (
            <button
              onClick={async () => {
                setAdminLoggingOut(true);
                try { await fetch("/api/v1/admin/logout", { method: "POST" }); } catch {}
                router.push("/admin/login");
              }}
              disabled={adminLoggingOut}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors disabled:opacity-50"
              aria-label="Admin Logout"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden md:inline">{adminLoggingOut ? "Logging out…" : "Logout"}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
