"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
  ExternalLink,
  LogOut,
  Swords,
  User,
  Shield,
  Menu,
  X,
} from "lucide-react";
import { useSession } from "@/context/SessionContext";
import TokenDisplay from "@/components/TokenDisplay";

export default function Header() {
  const { isAuthenticated, isHydrated, email, logout } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [adminLoggingOut, setAdminLoggingOut] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const showAuth = isHydrated && isAuthenticated;
  const isAdmin =
    pathname.startsWith("/admin") && !pathname.startsWith("/admin/login");
  const isLandingOrPublic =
    pathname === "/" || pathname === "/open-source" || pathname === "/release-notes";
  const isOpenSource = pathname === "/open-source";

  // Active link helper
  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  const navLinkClass = (href: string) =>
    `text-sm transition-colors ${
      isActive(href)
        ? "text-brand-blue font-medium"
        : "text-brand-charcoal hover:text-brand-blue"
    }`;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-brand-offwhite">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-2 md:px-6">
        {/* Logo — always links to landing page */}
        <Link href="/" className="flex items-center gap-2 flex-shrink-0">
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

        {/* Nav — right-aligned */}
        <nav
          className="hidden items-center gap-4 ml-auto md:flex"
          aria-label="Main navigation"
        >
          {/* Authenticated nav: Arena + Profile */}
          {showAuth && !isAdmin && (
            <>
              <Link href="/arena" className={`flex items-center gap-1 ${navLinkClass("/arena")}`}>
                <Swords className="h-3.5 w-3.5" />
                Arena
              </Link>
              <Link href="/profile" className={`flex items-center gap-1 ${navLinkClass("/profile")}`}>
                <User className="h-3.5 w-3.5" />
                Profile
              </Link>
            </>
          )}

          {/* Admin nav */}
          {isAdmin && (
            <Link href="/admin" className={`flex items-center gap-1 ${navLinkClass("/admin")}`}>
              <Shield className="h-3.5 w-3.5" />
              Admin
            </Link>
          )}

          {/* Public nav: Open Source, JuntoAI, GitHub */}
          {isLandingOrPublic && (
            <>
              {!isOpenSource && (
                <Link
                  href="/open-source"
                  className={navLinkClass("/open-source")}
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
            </>
          )}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-2 md:gap-3">
          {/* Auth info — email + tokens (desktop) */}
          {showAuth && !isAdmin && (
            <>
              <TokenDisplay />
            </>
          )}

          {/* Single logout button — adapts label for admin */}
          {(showAuth || isAdmin) && (
            <button
              onClick={async () => {
                if (isAdmin) {
                  setAdminLoggingOut(true);
                  try {
                    await fetch("/api/v1/admin/logout", { method: "POST" });
                  } catch {}
                  // Also logout user session if authenticated
                  if (showAuth) logout();
                  else router.push("/admin/login");
                } else {
                  logout();
                }
              }}
              disabled={adminLoggingOut}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors disabled:opacity-50"
              aria-label={isAdmin ? "Admin Logout" : "Logout"}
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden md:inline">
                {adminLoggingOut ? "Logging out…" : isAdmin ? "Admin Logout" : "Logout"}
              </span>
            </button>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors md:hidden"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileMenuOpen && (
        <div className="border-t border-gray-100 bg-brand-offwhite px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-3" aria-label="Mobile navigation">
            {showAuth && !isAdmin && (
              <>
                <Link
                  href="/arena"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2 ${navLinkClass("/arena")}`}
                >
                  <Swords className="h-4 w-4" />
                  Arena
                </Link>
                <Link
                  href="/profile"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-2 ${navLinkClass("/profile")}`}
                >
                  <User className="h-4 w-4" />
                  Profile
                </Link>
                {email && (
                  <span className="text-xs text-gray-400 truncate">{email}</span>
                )}
              </>
            )}

            {isAdmin && (
              <Link
                href="/admin"
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2 ${navLinkClass("/admin")}`}
              >
                <Shield className="h-4 w-4" />
                Admin Dashboard
              </Link>
            )}

            {isLandingOrPublic && (
              <>
                {!isOpenSource && (
                  <Link
                    href="/open-source"
                    onClick={() => setMobileMenuOpen(false)}
                    className={navLinkClass("/open-source")}
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
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
