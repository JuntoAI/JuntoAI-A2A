import type { Metadata } from "next";
import Script from "next/script";
import Providers from "@/components/Providers";
import Footer from "@/components/Footer";
import CookieBanner from "@/components/CookieBanner";
import "./globals.css";

const GA_ID = "G-ZW81C8NCRY";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://app.juntoai.org"
  ),
  title: {
    default: "JuntoAI — AI Agent Negotiation Sandbox | A2A Protocol",
    template: "%s | JuntoAI",
  },
  description:
    "JuntoAI A2A is a protocol-level sandbox where autonomous AI agents negotiate deals in real time. Pick a scenario, inject hidden variables, and watch AI reasoning live.",
  keywords: [
    "AI negotiation",
    "AI agents",
    "A2A protocol",
    "autonomous agents",
    "LLM negotiation",
    "agent-to-agent",
    "JuntoAI",
    "AI sandbox",
    "multi-agent simulation",
  ],
  authors: [{ name: "JuntoAI", url: "https://juntoai.org" }],
  creator: "JuntoAI",
  publisher: "JuntoAI",
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "/",
    siteName: "JuntoAI A2A Protocol Sandbox",
    title: "JuntoAI — AI Agent Negotiation Sandbox",
    description:
      "Watch autonomous AI agents negotiate deals in real time. Pick a scenario, flip hidden variables, and see how information asymmetry changes the outcome.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "JuntoAI A2A Protocol Sandbox — AI agents negotiating in real time",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@JuntoAI",
    creator: "@JuntoAI",
    title: "JuntoAI — AI Agent Negotiation Sandbox",
    description:
      "Watch autonomous AI agents negotiate deals in real time. Config-driven scenarios with hidden variables that visibly alter outcomes.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: "/",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <Script
          src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`}
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('consent', 'default', {
              analytics_storage: localStorage.getItem('cookieConsent') === 'accepted' ? 'granted' : 'denied'
            });
            gtag('js', new Date());
            gtag('config', '${GA_ID}');
          `}
        </Script>
      </head>
      <body className="flex min-h-screen flex-col">
        <Providers>
          <div className="flex-1">{children}</div>
          <Footer />
          <CookieBanner />
        </Providers>
      </body>
    </html>
  );
}
