export default function AboutPage() {
  const wide = window.innerWidth > 1024;
  return <h1 data-testid="heading">{wide ? "About us" : "About"}</h1>;
}
