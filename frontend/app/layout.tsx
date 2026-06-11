import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ReviewLens — App Review Intelligence Dashboard",
  description: "Explore rating/sentiment trends and ask natural-language questions over Google Play and Apple App Store reviews.",
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='%236366f1'/><stop offset='100%' stop-color='%23a855f7'/></linearGradient></defs><circle cx='45' cy='45' r='28' fill='none' stroke='url(%23g)' stroke-width='10'/><path d='M30 30 A 20 20 0 0 1 60 30' fill='none' stroke='white' stroke-width='4' stroke-linecap='round' opacity='0.6'/><line x1='65' y1='65' x2='90' y2='90' stroke='url(%23g)' stroke-width='12' stroke-linecap='round'/></svg>",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-[#0B0F19] text-[#F3F4F6] antialiased`}>
        {children}
      </body>
    </html>
  );
}
