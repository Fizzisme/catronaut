import { cookies } from "next/headers";

export default async function Home() {
  const theme = (await cookies()).get("theme");
  return <h1 data-testid="heading">Theme: {theme?.value}</h1>;
}
