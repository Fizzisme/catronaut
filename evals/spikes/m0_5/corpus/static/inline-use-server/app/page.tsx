export default function Home() {
  async function subscribe(formData: FormData) {
    "use server";
    console.log("subscribed", formData.get("email"));
  }
  return (
    <form action={subscribe} data-testid="heading">
      <input name="email" defaultValue="a@b.c" />
      <button type="submit">Subscribe</button>
    </form>
  );
}
