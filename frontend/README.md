# Front React — Contract Intelligence (CLM souverain)

SCAFFOLD du front (Vite + TypeScript + React 18) — **epic #69**.
Couvre les tickets #54 (Keycloak OIDC), #55 (upload + suivi statut), #56 (validation
HITL pdf.js + bbox), #57 (tableau de bord échéances + abonnement ICS).

> **Statut : SCAFFOLD.** Les fichiers source sont en place mais **aucun build n'a été
> lancé** (environnement sans réseau : impossible de télécharger les paquets npm).
> `npm install` puis `npm run build` **restent à exécuter**. La mise en place de la CI
> front est un TODO du ticket **#6**.

## Démarrage (dev)

```bash
cd frontend
cp .env.example .env        # puis adapter les URLs (API + Keycloak)
npm install                 # à exécuter (réseau requis)
npm run dev                 # serveur Vite sur http://localhost:5173
```

Build de production : `npm run build` (puis `npm run preview` pour vérifier).

## Variables d'environnement (`.env`)

| Variable                   | Rôle                                   | Défaut dev              |
| -------------------------- | -------------------------------------- | ----------------------- |
| `VITE_API_URL`             | URL de l'API FastAPI                   | `http://localhost:8000` |
| `VITE_KEYCLOAK_URL`        | Base Keycloak                          | `http://localhost:8080` |
| `VITE_KEYCLOAK_REALM`      | Realm OIDC                             | `clm`                   |
| `VITE_KEYCLOAK_CLIENT_ID`  | Client public SPA (PKCE)               | `clm-spa`               |

En dev, `vite.config.ts` proxifie `/uploads`, `/statut`, `/hitl`, `/ics`, `/recherche`
vers `VITE_API_URL` (évite les soucis CORS locaux).

## Structure

```
frontend/
  index.html, vite.config.ts, tsconfig.json, package.json, .env.example
  src/
    main.tsx              # bootstrap : init OIDC avant le rendu
    App.tsx               # coquille + navigation par onglets
    auth/keycloak.ts      # init keycloak-js (PKCE), token + tenant depuis le token
    api/client.ts         # fetch wrapper (bearer auto) + PUT direct S3
    pages/Upload.tsx      # presign → PUT S3 → confirm → polling statut (#55)
    pages/Validation.tsx  # pdf.js + overlay bbox provenance, valider/rejeter (#56)
    pages/Echeances.tsx   # tableau échéances + abonnement ICS (#57)
```

## Endpoints API consommés (alignés sur l'API FastAPI existante)

- `POST /uploads/presign` → `{ url, methode, cle, bucket, expire_dans }`
- `PUT <url présignée>` (direct navigateur → S3/Garage)
- `POST /uploads/confirm` → `202 { cle, etat }`
- `GET /statut/{workflow_id}` → `{ workflow_id, statut }`
- `GET /hitl/file`, `POST /hitl/contrats/{id}/valider`, `POST /hitl/contrats/{id}/rejeter`
- `POST /ics/abonnement` → `201 { id, url }`

Certains endpoints (file HITL #35, recherche facette #52) renvoient encore `501` côté
API : les pages retombent alors sur un jeu d'exemple, sans casser l'UI.

## Rappels garde-fous (spec §2.1, §2.6, §7)

- **Upload présigné navigateur → S3** : les octets ne transitent JAMAIS par l'API.
  Le SHA256 est calculé côté navigateur (clé canonique, idempotence).
- **Le tenant vient du token Keycloak**, JAMAIS saisi ni envoyé par le client. Le front
  ne le lit que pour l'affichage ; l'API le redérive elle-même du token.
- **Gate HITL non négociable** : aucune donnée `à_valider` ne doit être présentée comme
  validée ; seul un contrat validé entre dans alertes / ICS / index.
- **Date actionnable = date limite de dénonciation** (échéance − préavis), pas l'échéance.
- **ICS = visibilité seulement** : l'URL d'abonnement est un token capability révocable ;
  le feed ne contient que dates + intitulés, jamais le contenu des clauses.
