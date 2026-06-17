import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TOI OLT Manager",
  description: "Administracion GPON para TOI Internet",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
