import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <div className="font-sans">{children}</div>;
}
