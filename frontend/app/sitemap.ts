import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://app.juntoai.org";

  return [
    {
      url: baseUrl,
      lastModified: new Date("2026-04-01"),
      changeFrequency: "monthly",
      priority: 1,
    },
    {
      url: `${baseUrl}/release-notes`,
      lastModified: new Date("2026-04-01"),
      changeFrequency: "monthly",
      priority: 0.7,
    },
  ];
}
