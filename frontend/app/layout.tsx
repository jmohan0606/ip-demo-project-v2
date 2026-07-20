import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "iPerform Insights & Coaching", description: "Enterprise advisor intelligence, coaching, recommendations and agentic AI." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
