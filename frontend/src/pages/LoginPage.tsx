import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd logowania");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card narrow">
      <h1>Zaloguj się</h1>
      <p className="muted">
        Podstawowa wersja — bez hasła. Wpisz nazwę użytkownika (litery, cyfry,{" "}
        <code>_-. </code>). Jeśli nie istnieje, zostanie utworzona.
      </p>
      <form onSubmit={onSubmit} className="form">
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="np. ania"
            autoFocus
            required
            pattern="[a-zA-Z0-9_\-.]+"
            maxLength={64}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primary" type="submit" disabled={loading || !username.trim()}>
          {loading ? "Logowanie…" : "Wejdź"}
        </button>
      </form>
    </div>
  );
}
