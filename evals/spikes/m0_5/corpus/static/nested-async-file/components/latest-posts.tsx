import { posts } from "@/lib/posts";

export async function LatestPosts() {
  const latest = await Promise.resolve(posts.slice(0, 1));
  return <ul>{latest.map((post) => <li key={post.slug}>{post.title}</li>)}</ul>;
}
