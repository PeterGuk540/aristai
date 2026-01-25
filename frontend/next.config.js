/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // Preserve trailing slashes in API routes to avoid 308 redirects
  skipTrailingSlashRedirect: true,
}

module.exports = nextConfig
