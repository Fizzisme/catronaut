import { use } from "react";
import { notFound } from "next/navigation";
import { getPost } from "@/lib/posts";

export default function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const post = getPost(slug);
  if (!post) notFound();
  return <h1 data-testid="heading">{post.titel}</h1>;
}
