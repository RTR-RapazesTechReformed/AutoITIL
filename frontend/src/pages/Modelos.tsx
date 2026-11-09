import { useSearchParams } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import Qualidade from './modelos/Qualidade'
import Desempenho from './modelos/Desempenho'

type Aba = 'qualidade' | 'desempenho'

function resolveAba(valor: string | null): Aba {
  return valor === 'desempenho' ? 'desempenho' : 'qualidade'
}

function Modelos() {
  const [searchParams, setSearchParams] = useSearchParams()
  const aba = resolveAba(searchParams.get('aba'))

  function handleAbaChange(novaAba: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('aba', novaAba)
        return next
      },
      { replace: true },
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Modelos</h1>
      </div>

      <Tabs value={aba} onValueChange={handleAbaChange}>
        <TabsList>
          <TabsTrigger value="qualidade">Qualidade</TabsTrigger>
          <TabsTrigger value="desempenho">Desempenho</TabsTrigger>
        </TabsList>
        <TabsContent value="qualidade" className="mt-4">
          <Qualidade />
        </TabsContent>
        <TabsContent value="desempenho" className="mt-4">
          <Desempenho />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default Modelos
