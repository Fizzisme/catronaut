"use client";

import { useEffect } from "react";

export default function Home() {
  useEffect(() => {
    Promise.reject(new Error("rejected in effect"));
  }, []);
  return <h1 data-testid="heading">Home</h1>;
}
