import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "App Review Intelligence — PM Dashboard",
  description: "Explore rating/sentiment trends and ask natural-language questions over Google Play and Apple App Store reviews.",
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
