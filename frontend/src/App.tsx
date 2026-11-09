import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Ingestao from './pages/Ingestao'
import Kanban from './pages/Kanban'
import Operacao from './pages/Operacao'
import Modelos from './pages/Modelos'
import HistoricoUploads from './pages/HistoricoUploads'
import Usuarios from './pages/admin/Usuarios'
import Custos from './pages/Custos'
import ToastViewport from './components/ToastViewport'
import { ToastProvider } from './lib/toast'

function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/ingestao" element={<Ingestao />} />
              <Route path="/kanban" element={<Kanban />} />
              <Route path="/operacao" element={<Operacao />} />
              <Route path="/modelos" element={<Modelos />} />
              <Route path="/historico-uploads" element={<HistoricoUploads />} />
              <Route path="/custos" element={<Custos />} />
              <Route path="/admin/usuarios" element={<Usuarios />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
      <ToastViewport />
    </ToastProvider>
  )
}

export default App
