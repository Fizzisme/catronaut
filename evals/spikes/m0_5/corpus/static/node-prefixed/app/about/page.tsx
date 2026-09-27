import path from "node:path";

export default function AboutPage() {
  return <h1 data-testid="heading">{path.join("about", "us")}</h1>;
}
