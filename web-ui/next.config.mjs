/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['ag-grid-react', 'ag-grid-community', 'ag-grid-enterprise'],
  serverExternalPackages: ['cytoscape'],
};

export default nextConfig;
