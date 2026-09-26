export const posts = [
  { slug: "hello-world", title: "Hello, world", body: "The first post." },
  { slug: "second-post", title: "Second post", body: "Another one." },
];

export function getPost(slug: string) {
  return posts.find((post) => post.slug === slug);
}
