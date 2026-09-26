import { notFound } from "next/navigation";
import { getPost } from "@/lib/posts";

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();
  return (
    <article>
      <h1 className="font-display text-4xl" data-testid="heading">{post.title}</h1>
      <p className="mt-2" data-testid="slug">{slug}</p>
    </article>
  );
}
