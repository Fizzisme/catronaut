"use client";

import { useState } from "react";

export function Counter() {
  const [count, setCount] = useState(0);
  return (
    <button className="rounded border px-3 py-1" onClick={() => setCount(count + "1")} data-testid="counter">
      Clicked {count}
    </button>
  );
}
