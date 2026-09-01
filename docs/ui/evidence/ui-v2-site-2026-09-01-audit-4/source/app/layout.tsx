import type { Metadata } from "next";
import "./globals.css";

const siteUrl = "https://woff-mate-ui-v2.pilotohans.chatgpt.site";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "WoFF Mate UI V2",
  description: "An interactive, read-only Operations Board, Pilot Dossier, Mission Log, Squadron Roster, War Diary, Reports Library and System Status prototype for the WoFF Mate campaign companion.",
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  openGraph: {
    type: "website",
    url: siteUrl,
    title: "WoFF Mate UI V2",
    description: "Operations Board · Read-only prototype",
    images: [{ url: `${siteUrl}/og.png`, width: 1731, height: 909, alt: "WoFF Mate UI V2 — Operations Board read-only prototype" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "WoFF Mate UI V2",
    description: "Operations Board · Read-only prototype",
    images: [`${siteUrl}/og.png`],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
