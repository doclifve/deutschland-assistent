import "./styles.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Deutschland Assistent",
  description: "Behördenpost. Endlich verständlich. Brief fotografieren, verstehen, was drinsteht, wissen, was zu tun ist.",
  icons: { icon: "/logo.svg" },
  appleWebApp: { capable: true, title: "Deutschland Assistent", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#FFFFFF",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
