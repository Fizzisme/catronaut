import localFont from "next/font/local";

const brand = localFont({ src: "./brand.woff2" });

export default function AboutPage() {
  return <h1 className={brand.className} data-testid="heading">About us</h1>;
}
