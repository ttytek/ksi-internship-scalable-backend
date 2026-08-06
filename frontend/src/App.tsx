import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import LoginPage from "./pages/LoginPage";
import RankingPage from "./pages/RankingPage";
import SubmissionPage from "./pages/SubmissionPage";
import SubmissionsPage from "./pages/SubmissionsPage";
import TaskPage from "./pages/TaskPage";
import TasksPage from "./pages/TasksPage";

function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      <header className="header">
        <div className="header-inner">
          <Link to="/" className="brand">
            KSI
          </Link>
          <nav className="nav">
            <Link to="/">Zadania</Link>
            <Link to="/ranking">Ranking</Link>
            {user && <Link to="/submissions">Moje zgłoszenia</Link>}
          </nav>
          <div className="header-user">
            {user ? (
              <>
                <span className="muted">@{user.username}</span>
                <button type="button" className="btn ghost" onClick={logout}>
                  Wyloguj
                </button>
              </>
            ) : (
              <Link to="/login" className="btn">
                Zaloguj
              </Link>
            )}
          </div>
        </div>
      </header>
      <main className="main">{children}</main>
      <footer className="footer">
        <span className="muted">Prosta platforma zadań programistycznych</span>
      </footer>
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<TasksPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/tasks/:taskId" element={<TaskPage />} />
        <Route
          path="/submissions"
          element={
            <RequireAuth>
              <SubmissionsPage />
            </RequireAuth>
          }
        />
        <Route path="/submissions/:submissionId" element={<SubmissionPage />} />
        <Route path="/ranking" element={<RankingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
