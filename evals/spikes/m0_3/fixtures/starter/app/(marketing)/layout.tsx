export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return <div className="rounded-3xl bg-brand/10 p-8" data-testid="marketing-layout">{children}</div>;
}
