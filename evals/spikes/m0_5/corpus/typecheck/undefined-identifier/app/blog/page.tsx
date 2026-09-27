import Link from "next/link";
import { posts } from "@/lib/posts";

export default function BlogIndex() {
  return (
    <ul data-testid="heading">
      {postz.map((post) => (
        <li key={post.slug}>
          <Link href={`/blog/${post.slug}`}>{post.title}</Link>
        </li>
      ))}
    </ul>
  );
}
