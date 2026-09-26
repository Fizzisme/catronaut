"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export function Counter() {
  const [count, setCount] = useState(0);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  return (
    <div className="mt-8 flex items-center gap-4">
      <button className="rounded border px-3 py-1" onClick={() => setCount(count + 1)} data-testid="counter">
        Clicked {count}
      </button>
      <button className="rounded border px-3 py-1" onClick={() => router.push("/about?from=home")} data-testid="push">
        router.push
      </button>
      <span data-testid="location">{pathname}{searchParams.toString() ? `?${searchParams}` : ""}</span>
    </div>
  );
}
