import "./globals.css";

export const metadata = {
  title: "Genlineage . Git for generative media",
  description:
    "Every generation has a history. Content-addressed commits, remix DAGs, agentic quality gates, signed provenance.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Workbench&family=Space+Grotesk:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
