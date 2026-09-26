import Image from "next/image";
import Link from "next/link";
import { Counter } from "@/components/counter";

export default function Home() {
  return (
    <section className="grid gap-8 md:grid-cols-2">
      <div>
        <h1 className="font-display text-6xl font-bold leading-tight" data-testid="heading">
          Make it <span className="text-brand">bold</span>.
        </h1>
        <p className="mt-4 max-w-md text-lg text-stone-600">A frontend-only Next.js project running in the preview.</p>
        <Link href="/blog/hello-world" className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-white">
          Read the first post
        </Link>
        <Counter />
      </div>
      <div className="relative aspect-[4/3] overflow-hidden rounded-3xl">
        <Image
          src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1200"
          alt="Landscape"
          fill
          priority
          className="object-cover"
        />
      </div>
    </section>
  );
}
