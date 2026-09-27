import { use } from "react";
import { getPost } from "@/lib/posts";

export default function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const post = getPost(slug);
  return <h1 data-testid="heading">{post.title}</h1>;
}
