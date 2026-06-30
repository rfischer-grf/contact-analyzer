/**
 * Coquille applicative (shell) du cockpit Clausio — tickets #72/#73/#74.
 *
 * Routage `react-router-dom` : toutes les routes sont protégées par `AuthProvider`
 * + `RouteProtegee`, et rendues dans `AppLayout` (sidebar + en-tête tenant + zone
 * de contenu). Les pages métier sont écrites par d'autres agents ; on les importe
 * par chemin (`pages/…`) et on câble les routes de l'epic #88.
 */
import { Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RouteProtegee } from "./auth/AuthContext";
import { AppLayout } from "./components/layout/AppLayout";
import { tokens } from "./theme";

// Pages métier (propriété d'autres agents — importées par chemin).
import { Dashboard } from "./pages/Dashboard";
import { Contrats } from "./pages/Contrats";
import { ContratDetail } from "./pages/ContratDetail";
import { Upload } from "./pages/Upload";
import { Validation } from "./pages/Validation";
import { Projection } from "./pages/Projection";
import { Recherche } from "./pages/Recherche";
import { Echeances } from "./pages/Echeances";

/** Repli affiché pendant le chargement d'une page (Suspense). */
function Chargement(): JSX.Element {
  return (
    <p style={{ padding: tokens.espacements.xl, color: tokens.couleurs.texteAttenue }}>
      Chargement…
    </p>
  );
}

/** Route inconnue → renvoi au tableau de bord. */
function Inconnue(): JSX.Element {
  return <Navigate to="/" replace />;
}

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RouteProtegee>
          <Suspense fallback={<Chargement />}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/contrats" element={<Contrats />} />
                <Route path="/contrats/:id" element={<ContratDetail />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/validation" element={<Validation />} />
                <Route path="/validation/:id" element={<Validation />} />
                <Route path="/projection/:id" element={<Projection />} />
                <Route path="/recherche" element={<Recherche />} />
                <Route path="/echeances" element={<Echeances />} />
                <Route path="*" element={<Inconnue />} />
              </Route>
            </Routes>
          </Suspense>
        </RouteProtegee>
      </AuthProvider>
    </BrowserRouter>
  );
}
