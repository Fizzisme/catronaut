export default function AboutPage() {
  const team = ["Ada", "Linus"];
  if (team.length > 0) {
    return <h1 data-testid="heading">About us</h1>;
  return null;
}
