import { createBrowserRouter } from "react-router";
import { Shell } from "./Shell";
import { AuthGate } from "./AuthGate";
import { SetupPage } from "@/features/setup/SetupPage";
import { LoginPage } from "@/features/login/LoginPage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { MapPage } from "@/features/map/MapPage";
import { DevicesPage } from "@/features/devices/DevicesPage";
import { DeviceDetailPage } from "@/features/devices/DeviceDetailPage";
import { FencesPage } from "@/features/fences/FencesPage";
import { FenceEditorPage } from "@/features/fences/FenceEditorPage";

export const router = createBrowserRouter([
  { path: "/setup", element: <SetupPage /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: <AuthGate />,
    children: [
      {
        element: <Shell />,
        children: [
          { path: "/", element: <OverviewPage /> },
          { path: "/map", element: <MapPage /> },
          { path: "/devices", element: <DevicesPage /> },
          { path: "/devices/:id", element: <DeviceDetailPage /> },
          { path: "/fences", element: <FencesPage /> },
          { path: "/fences/new", element: <FenceEditorPage /> },
          { path: "/fences/:id", element: <FenceEditorPage /> },
        ],
      },
    ],
  },
]);
