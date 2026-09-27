import Image from "next/image";

export default function AboutPage() {
  return (
    <div className="relative h-64" data-testid="heading">
      <Image src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1200" fill />
    </div>
  );
}
