import { useState } from "react";
import { getTenant, getUtilisateur, logout } from "./auth/keycloak";
import { Upload } from "./pages/Upload";
import { Validation } from "./pages/Validation";
import { Echeances } from "./pages/Echeances";

type Onglet = "upload" | "validation" | "echeances";

const ONGLETS: { cle: Onglet; libelle: string }[] = [
  { cle: "upload", libelle: "Déposer un contrat" },
  { cle: "validation", libelle: "Validation (HITL)" },
  { cle: "echeances", libelle: "Échéances" },
];

/**
 * Coquille applicative (scaffold #69). Navigation par onglets minimale ;
 * un vrai routeur (react-router) sera ajouté au besoin dans un ticket dédié.
 */
export function App(): JSX.Element {
  const [onglet, setOnglet] = useState<Onglet>("upload");

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1000, margin: "0 auto", padding: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h1 style={{ fontSize: 20 }}>Contract Intelligence — CLM souverain</h1>
        <span style={{ fontSize: 13, color: "#555" }}>
          {getUtilisateur()} · tenant&nbsp;<strong>{getTenant() ?? "—"}</strong>{" "}
          <button onClick={logout} style={{ marginLeft: 8 }}>
            Se déconnecter
          </button>
        </span>
      </header>

      <nav style={{ display: "flex", gap: 8, borderBottom: "1px solid #ddd", margin: "12px 0" }}>
        {ONGLETS.map(({ cle, libelle }) => (
          <button
            key={cle}
            onClick={() => setOnglet(cle)}
            aria-current={onglet === cle}
            style={{
              border: "none",
              borderBottom: onglet === cle ? "2px solid #2557d6" : "2px solid transparent",
              background: "none",
              padding: "6px 10px",
              fontWeight: onglet === cle ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {libelle}
          </button>
        ))}
      </nav>

      <main>
        {onglet === "upload" && <Upload />}
        {onglet === "validation" && <Validation />}
        {onglet === "echeances" && <Echeances />}
      </main>
    </div>
  );
}
