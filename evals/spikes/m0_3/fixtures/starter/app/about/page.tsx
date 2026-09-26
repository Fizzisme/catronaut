import type { Metadata } from "next";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return <h1 className="font-display text-4xl" data-testid="heading">About us</h1>;
}
