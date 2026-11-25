import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: "/little-fortune",
  output: "export",
  // The live site serves the page at /horoscope/ (horoscope/index.html),
  // not /horoscope.html.
  trailingSlash: true,
};

export default nextConfig;
