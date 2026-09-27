export default function AboutPage() {
  const team = await Promise.resolve(["Ada", "Linus"]);
  return <h1 data-testid="heading">{team.join(", ")}</h1>;
}
