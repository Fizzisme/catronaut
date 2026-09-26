async function Team() {
  const members = await Promise.resolve(["Ada", "Linus"]);
  return <ul>{members.map((m) => <li key={m}>{m}</li>)}</ul>;
}

export default function AboutPage() {
  return (
    <section data-testid="heading">
      <h1>About us</h1>
      <Team />
    </section>
  );
}
