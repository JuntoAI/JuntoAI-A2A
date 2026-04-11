import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://app.juntoai.org";

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/arena/", "/api/", "/admin/", "/profile/"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
