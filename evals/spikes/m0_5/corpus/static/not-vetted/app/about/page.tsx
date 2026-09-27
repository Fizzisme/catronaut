"use client";

import axios from "axios";
import { useEffect, useState } from "react";

export default function AboutPage() {
  const [title, setTitle] = useState("About us");
  useEffect(() => {
    axios.get<{ title: string }>("https://example.com/about.json").then((r) => setTitle(r.data.title));
  }, []);
  return <h1 data-testid="heading">{title}</h1>;
}
