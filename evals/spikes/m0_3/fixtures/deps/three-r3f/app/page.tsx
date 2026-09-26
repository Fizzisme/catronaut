"use client";

import dynamic from "next/dynamic";

const Scene = dynamic(() => import("@/components/scene"), { ssr: false });

export default function Home() {
  return (
    <section>
      <h1 data-testid="heading" className="font-display text-6xl">Three + R3F</h1>
      <div className="mt-6 h-[420px] w-full rounded-3xl bg-stone-200">
        <Scene />
      </div>
    </section>
  );
}
