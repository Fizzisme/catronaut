export function Badge({ count }: { count: number }) {
  return <span className="rounded-full bg-brand px-2 text-white">{count}</span>;
}
