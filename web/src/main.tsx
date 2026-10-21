import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans-condensed/500.css";
import "@fontsource/ibm-plex-sans-condensed/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Rail } from "./components/Rail";
import { ThemeProvider } from "./lib/theme";
import Analyze from "./pages/Analyze";
import DataAdmin from "./pages/DataAdmin";
import History from "./pages/History";
import Report from "./pages/Report";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

function NotFound() {
  return (
    <div>
      <h1 className="font-cond text-[2rem] font-semibold">Page not found</h1>
      <a href="/" className="text-cobalt hover:underline">
        Go to New analysis
      </a>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 bg-surface px-3 py-2 rounded-md">
            Skip to content
          </a>
          <Rail />
          <main id="main" className="md:pl-56">
            <div className="mx-auto max-w-[1240px] px-4 sm:px-8 py-8 md:py-12">
              <Routes>
                <Route path="/" element={<Analyze />} />
                <Route path="/runs/:runId" element={<Report />} />
                <Route path="/history" element={<History />} />
                <Route path="/data" element={<DataAdmin />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </div>
          </main>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
