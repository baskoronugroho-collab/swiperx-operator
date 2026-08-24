import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./lib/auth";
import type { Role } from "./lib/api";
import { Spinner } from "./components/ui";
import Shell from "./components/Shell";
import SignIn from "./pages/SignIn";
import OrderCreation from "./pages/OrderCreation";
import IntakeHistory from "./pages/IntakeHistory";
import CourierLinks from "./pages/CourierLinks";
import Users from "./pages/Users";
import IntakeDetailPage from "./pages/IntakeDetail";
import RejectReturns from "./pages/RejectReturns";
import ManualLink from "./pages/ManualLink";
import CourierApp from "./pages/courier/CourierApp";

function Protected({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user, loading, has } = useAuth();
  if (loading)
    return (
      <div className="grid h-dvh place-items-center">
        <Spinner label="Loading…" />
      </div>
    );
  if (!user) return <Navigate to="/signin" replace />;
  if (!has(...roles))
    return (
      <div className="grid h-dvh place-items-center px-6 text-center">
        <div>
          <p className="text-lg font-bold">No access to this page</p>
          <p className="mt-2 max-w-sm text-sm text-ink-muted">
            Your account doesn’t hold a role for this area. Contact the Ninja Van team to have a
            role assigned.
          </p>
        </div>
      </div>
    );
  return <>{children}</>;
}

const OPS: Role[] = ["implant", "de", "station_ic", "program_manager"];
const INTAKE: Role[] = ["implant", "de"];

function Router() {
  return (
    <Routes>
      {/* Courier link — unauthenticated, the token is the credential. Must stay
          outside <Protected> and outside the staff shell. */}
      <Route path="/c/:token" element={<CourierApp />} />

      <Route path="/signin" element={<SignIn />} />

      <Route
        element={
          <Protected roles={[...OPS, "validator", "swiperx"]}>
            <Shell />
          </Protected>
        }
      >
        <Route index element={<Navigate to="/orders/new" replace />} />
        <Route
          path="/orders/new"
          element={
            <Protected roles={INTAKE}>
              <OrderCreation />
            </Protected>
          }
        />
        <Route
          path="/links"
          element={
            <Protected roles={[...INTAKE, "station_ic"]}>
              <CourierLinks />
            </Protected>
          }
        />
        <Route
          path="/orders"
          element={
            <Protected roles={INTAKE}>
              <IntakeHistory />
            </Protected>
          }
        />
        <Route
          path="/orders/:id"
          element={
            <Protected roles={INTAKE}>
              <IntakeDetailPage />
            </Protected>
          }
        />
        <Route
          path="/returns"
          element={
            <Protected roles={[...OPS, "validator"]}>
              <RejectReturns />
            </Protected>
          }
        />
        {/* Phase-1 field test. Intake roles can run it; it never touches a real intake. */}
        <Route
          path="/manual"
          element={
            <Protected roles={INTAKE}>
              <ManualLink />
            </Protected>
          }
        />
        <Route
          path="/users"
          element={
            <Protected roles={["superadmin"]}>
              <Users />
            </Protected>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router />
    </AuthProvider>
  );
}
