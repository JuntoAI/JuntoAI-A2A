import type { Metadata } from "next";
import Script from "next/script";
import Providers from "@/components/Providers";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import CookieBanner from "@/components/CookieBanner";
import "./globals.css";

const GA_ID = "G-ZW81C8NCRY";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://app.juntoai.org"
  ),
  title: {
    default: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    template: "%s | JuntoAI",
  },
  description:
    "Rehearse sales deals against AI buyers that push back, stall, and negotiate like real prospects. AI-powered deal rehearsal and sales training for teams that want to close with confidence.",
  keywords: [
    "sales training",
    "deal rehearsal",
    "objection handling",
    "sales enablement",
    "AI sales training",
    "sales simulation",
    "AI negotiation",
    "JuntoAI",
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
    siteName: "JuntoAI",
    title: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    description:
      "Rehearse sales deals against AI buyers that push back, stall, and negotiate like real prospects. AI-powered deal rehearsal and sales training for closing confidence.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "JuntoAI A2A Protocol Sandbox - AI agents negotiating in real time",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    site: "@JuntoAI",
    creator: "@JuntoAI",
    title: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    description:
      "Rehearse sales deals against AI buyers that push back, stall, and negotiate like real prospects. AI-powered deal rehearsal and sales training for closing confidence.",
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
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
        />
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
          <Header />
          <div className="flex-1">{children}</div>
          <Footer />
          <CookieBanner />
        </Providers>
      </body>
    </html>
  );
}
