import { subscribe } from "./actions";

export default function Home() {
  return (
    <form action={subscribe} data-testid="heading">
      <input name="email" defaultValue="a@b.c" />
      <button type="submit">Subscribe</button>
    </form>
  );
}
