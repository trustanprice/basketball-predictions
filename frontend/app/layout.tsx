import type { Metadata } from "next";
import { Bebas_Neue, IBM_Plex_Mono, Inter } from "next/font/google";
import { Nav } from "@/components/Nav";
import { GlobalEscapeToClose } from "@/components/GlobalEscapeToClose";
import "./globals.css";

const displayFont = Bebas_Neue({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
});

const monoFont = IBM_Plex_Mono({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-mono",
});

const bodyFont = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Basketball Predictions",
  description: "Win predictions, player power rankings, and coaching evaluation.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${displayFont.variable} ${monoFont.variable} ${bodyFont.variable}`}>
      <body className="min-h-screen bg-page text-ink antialiased">
        <GlobalEscapeToClose />
        <Nav />
        <main className="mx-auto max-w-5xl px-4 py-12 sm:px-8">{children}</main>
      </body>
    </html>
  );
}
