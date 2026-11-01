import { Navigate, Route, Routes } from "react-router-dom";
import { ActiveProvider } from "./active";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Customers from "./pages/Customers";
import Detections from "./pages/Detections";
import Login from "./pages/Login";
import Queue from "./pages/Queue";
import Signatures from "./pages/Signatures";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <Protected>
            <ActiveProvider>
              <Layout>
                <Routes>
                  <Route path="/" element={<Queue />} />
                  <Route path="/detections" element={<Detections />} />
                  <Route path="/customers" element={<Customers />} />
                  <Route path="/signatures" element={<Signatures />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </ActiveProvider>
          </Protected>
        }
      />
    </Routes>
  );
}
