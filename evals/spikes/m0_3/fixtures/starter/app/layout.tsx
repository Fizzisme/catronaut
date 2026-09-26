import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const playfair = Playfair_Display({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-playfair" });

export const metadata: Metadata = {
  title: { template: "%s | Starter", default: "Starter" },
  description: "M0.3 preview starter",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable}`}>
      <body className="font-sans">
        <header className="flex gap-6 border-b border-stone-200 px-8 py-4" data-testid="nav">
          <Link href="/" className="font-display text-xl font-bold text-brand">Starter</Link>
          <Link href="/about">About</Link>
          <Link href="/blog">Blog</Link>
          <Link href="/pricing">Pricing</Link>
        </header>
        <main className="px-8 py-10">{children}</main>
      </body>
    </html>
  );
}
