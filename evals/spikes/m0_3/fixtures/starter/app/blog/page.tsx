import Link from "next/link";
import { posts } from "@/lib/posts";

export const metadata = { title: "Blog" };

export default function BlogIndex() {
  return (
    <ul className="space-y-2" data-testid="heading">
      {posts.map((post) => (
        <li key={post.slug}>
          <Link href={`/blog/${post.slug}`} className="underline">{post.title}</Link>
        </li>
      ))}
    </ul>
  );
}
