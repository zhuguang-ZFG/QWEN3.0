import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://donglicao.com";
  const paths = [
    "",
    "/pricing",
    "/product-draw",
    "/product-write",
    "/product-human",
    "/privacy",
    "/terms",
    "/developer/playground",
  ];
  return paths.map((path) => ({
    url: `${baseUrl}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" ? "daily" : "weekly",
    priority: path === "" ? 1.0 : 0.7,
  }));
}
