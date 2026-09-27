import { notFound } from "next/navigation";
import { getPost } from "@/lib/posts";

export default function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const post = getPost(params.slug);
  if (!post) notFound();
  return <h1 data-testid="heading">{post.title}</h1>;
}
