"use client";

import { useRouter } from "next/router";

export function Back() {
  const router = useRouter();
  return <button onClick={() => router.back()}>Back</button>;
}
