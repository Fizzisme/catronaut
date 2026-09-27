"use client";

import { useState } from "react";

export function Newsletter() {
  const [done, setDone] = useState(false);
  async function subscribe() {
    await fetch("/api/subscribe", { method: "POST", body: JSON.stringify({ email: "a@b.c" }) });
    setDone(true);
  }
  return <button onClick={subscribe}>{done ? "Thanks" : "Subscribe"}</button>;
}
