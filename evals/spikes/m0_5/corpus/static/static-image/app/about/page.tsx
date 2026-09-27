import Image from "next/image";
import hero from "./hero.png";

export default function AboutPage() {
  return <Image src={hero} alt="Team" data-testid="heading" />;
}
