import "server-only";

export const posts = [{ slug: "hello-world", title: "Hello, world", body: "The first post." }];

export function getPost(slug: string) {
  return posts.find((post) => post.slug === slug);
}
