# React + TypeScript + Vite

> **Note:** AutoITIL Frontend — Projeto React inicializado. Stack: Vite + React + TypeScript + Tailwind + shadcn/ui + Recharts.

## Como rodar

Este frontend depende do backend FastAPI para funcionar em desenvolvimento: `vite.config.ts` configura um proxy que encaminha todas as chamadas `/api/*` para `http://localhost:8000`.

1. **Suba o backend primeiro**, em outro terminal, a partir da raiz do repositório:

   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

   Isso deixa a API respondendo em `http://localhost:8000`.

2. **Copie o `.env.example`**:

   ```bash
   cp .env.example .env
   ```

3. **Instale as dependências e suba o frontend**, a partir de `frontend/`:

   ```bash
   npm install
   npm run dev
   ```

   O servidor de desenvolvimento sobe por padrão em `http://localhost:5173`.

4. Abra `http://localhost:5173` no navegador — mostra a landing (V2, Direção A "Pastel
   Flutuante"). O app operacional em si (upload, Kanban, Dashboard, Métricas)
   fica em `/ingestao`, `/kanban`, `/dashboard`, `/metricas`; a landing tem um botão "Entrar no
   app" para `/ingestao`. Se o Kanban/Dashboard não carregarem dados, confira se o backend está
   mesmo rodando em `:8000` (proxy de `/api/*`).

## Sobre o template

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
