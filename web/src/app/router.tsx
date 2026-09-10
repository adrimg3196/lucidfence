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
import { PoliciesPage } from "@/features/policies/PoliciesPage";
import { PolicyEditorPage } from "@/features/policies/PolicyEditorPage";
import { IncidentsPage } from "@/features/incidents/IncidentsPage";
import { IncidentDetailPage } from "@/features/incidents/IncidentDetailPage";
import { AlertsPage } from "@/features/alerts/AlertsPage";
import { PlaybooksPage } from "@/features/playbooks/PlaybooksPage";
import { PlaybookEditorPage } from "@/features/playbooks/PlaybookEditorPage";
import { HandoffsPage } from "@/features/handoffs/HandoffsPage";
import { EventsPage } from "@/features/events/EventsPage";
import { ActionsPage } from "@/features/actions/ActionsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";

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
          { path: "/policies", element: <PoliciesPage /> },
          { path: "/policies/new", element: <PolicyEditorPage /> },
          { path: "/policies/:id", element: <PolicyEditorPage /> },
          { path: "/incidents", element: <IncidentsPage /> },
          { path: "/incidents/:id", element: <IncidentDetailPage /> },
          { path: "/alerts", element: <AlertsPage /> },
          { path: "/playbooks", element: <PlaybooksPage /> },
          { path: "/playbooks/new", element: <PlaybookEditorPage /> },
          { path: "/playbooks/:id", element: <PlaybookEditorPage /> },
          { path: "/handoffs", element: <HandoffsPage /> },
          { path: "/events", element: <EventsPage /> },
          { path: "/actions", element: <ActionsPage /> },
          { path: "/settings", element: <SettingsPage /> },
        ],
      },
    ],
  },
]);
