import { readFileSync } from "fs";

export default function Home() {
  const text = readFileSync("/package.json", "utf8");
  return <pre data-testid="heading">{text}</pre>;
}
