import Image from "next/image";

export default function AboutPage() {
  return <Image src="/team.jpg" alt="Team" width={800} height={600} data-testid="heading" />;
}
