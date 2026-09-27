"use client";

import { useState } from "react";

export function Rating({ onRate }: { onRate: (value: number) => void }) {
  const [value, setValue] = useState(0);
  return (
    <div>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} onClick={() => { setValue(n); onRate(n); }}>
          {n <= value ? "★" : "☆"}
        </button>
      ))}
    </div>
  );
}
