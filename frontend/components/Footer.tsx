export default function Footer() {
  return (
    <footer className="w-full border-t border-gray-200 bg-brand-offwhite px-4 py-4 text-xs text-gray-500">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 sm:flex-row sm:justify-between">
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <span>© 2026 <a href="https://juntoai.org" target="_blank" rel="noopener noreferrer" className="hover:text-brand-blue transition-colors">JuntoAI</a> Limited</span>
          <span className="hidden sm:inline">·</span>
          <a href="https://juntoai.org/privacy-policy.html" target="_blank" rel="noopener noreferrer" className="hover:text-brand-blue transition-colors">Privacy Policy</a>
          <span className="hidden sm:inline">·</span>
          <a href="https://juntoai.org/terms-of-service.html" target="_blank" rel="noopener noreferrer" className="hover:text-brand-blue transition-colors">Terms of Service</a>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden md:inline text-gray-400">
            Registered in Ireland · CRO No. 807583
          </span>
          <a
            href="https://www.linkedin.com/company/juntoai"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="LinkedIn"
            className="text-gray-400 hover:text-brand-blue transition-colors"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
          </a>
          <a
            href="https://x.com/JuntoAI"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="X (Twitter)"
            className="text-gray-400 hover:text-brand-charcoal transition-colors"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}
