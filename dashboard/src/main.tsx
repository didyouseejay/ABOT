import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { BundleProvider } from "./data/BundleContext.tsx";
import "leaflet/dist/leaflet.css";
import "./styles/global.css";

const root = document.getElementById("root");
if (root === null) throw new Error("index.html has no #root element");

createRoot(root).render(
  <StrictMode>
    <BundleProvider>
      <App />
    </BundleProvider>
  </StrictMode>,
);
