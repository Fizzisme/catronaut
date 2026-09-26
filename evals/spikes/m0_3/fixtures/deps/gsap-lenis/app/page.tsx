"use client";

import { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { ReactLenis } from "lenis/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export default function Home() {
  const root = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      gsap.from("[data-testid=heading]", { y: 60, opacity: 0, duration: 0.6 });
      gsap.to("[data-testid=probe]", {
        rotate: 180,
        scrollTrigger: { trigger: "[data-testid=probe]", start: "top center", scrub: true },
      });
    },
    { scope: root },
  );
  return (
    <ReactLenis root>
      <div ref={root} className="space-y-6">
        <h1 data-testid="heading" className="font-display text-6xl">GSAP + Lenis</h1>
        <div className="h-[80vh]" />
        <div data-testid="probe" className="h-40 w-40 rounded-3xl bg-brand" />
        <div className="h-[80vh]" />
      </div>
    </ReactLenis>
  );
}
