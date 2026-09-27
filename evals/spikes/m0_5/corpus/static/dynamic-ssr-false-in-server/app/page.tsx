import dynamic from "next/dynamic";

const Globe = dynamic(() => import("@/components/globe"), { ssr: false });

export default function Home() {
  return (
    <section>
      <h1 data-testid="heading">Globe</h1>
      <Globe />
    </section>
  );
}
