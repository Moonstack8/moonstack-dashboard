import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import AccountView from './pages/AccountView'
import CampaignView from './pages/CampaignView'
import AdSetView from './pages/AdSetView'
import CampaignBuilder from './pages/CampaignBuilder'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="ml-60 flex-1 p-6 min-w-0">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/accounts/:accountId" element={<AccountView />} />
              <Route path="/campaigns/:campaignId" element={<CampaignView />} />
              <Route path="/adsets/:adsetId" element={<AdSetView />} />
              <Route path="/builder" element={<CampaignBuilder />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
