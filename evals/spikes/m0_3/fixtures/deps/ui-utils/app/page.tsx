import { ArrowRight, ShoppingCart } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: Parameters<typeof clsx>) {
  return twMerge(clsx(inputs));
}

export default function Home() {
  return (
    <section className="space-y-6">
      <h1 data-testid="heading" className="font-display text-6xl">UI utilities</h1>
      <button className={cn("flex items-center gap-2 rounded-full px-6 py-3", "bg-ink text-white", "px-8")} data-testid="probe">
        <ShoppingCart size={18} /> Add to cart <ArrowRight size={18} />
      </button>
    </section>
  );
}
