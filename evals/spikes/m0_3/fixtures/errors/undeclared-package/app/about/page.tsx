"use client";

import confetti from "canvas-confetti";

export default function AboutPage() {
  return <button onClick={() => confetti()} data-testid="heading">Celebrate</button>;
}
