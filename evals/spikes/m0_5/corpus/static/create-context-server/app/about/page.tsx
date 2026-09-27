import { ThemeProvider } from "@/components/theme";

export default function AboutPage() {
  return (
    <ThemeProvider>
      <h1 data-testid="heading">About us</h1>
    </ThemeProvider>
  );
}
