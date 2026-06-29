import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Infrastructure SaaS",
  description:
    "Describe your application; a multi-agent system designs infrastructure, estimates cost, generates deployments, and recommends optimizations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
