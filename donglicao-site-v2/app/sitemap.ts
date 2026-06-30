import type { MetadataRoute } from "next";
import { posts } from "./blog/posts";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = "https://www.donglicao.com";
  const paths = [
    "",
    "/pricing",
    "/product-draw",
    "/product-write",
    "/product-human",
    "/privacy",
    "/terms",
    "/developer/playground",
    "/login",
    "/register",
    "/en",
    "/en/pricing",
    "/en/product-draw",
    "/en/product-write",
    "/en/product-human",
    "/en/privacy",
    "/en/terms",
    "/blog",
    ...posts.map((post) => `/blog/${post.slug}`),
  ];
  return paths.map((path) => ({
    url: `${baseUrl}${path}`,
    lastModified: new Date(),
    changeFrequency: path === "" ? "daily" : "weekly",
    priority: path === "" ? 1.0 : 0.7,
  }));
}
