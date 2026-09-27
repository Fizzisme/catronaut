import { Rating } from "@/components/rating";

export default function AboutPage() {
  return (
    <section data-testid="heading">
      <h1>Rate us</h1>
      <Rating onRate={(value) => console.log("rated", value)} />
    </section>
  );
}
