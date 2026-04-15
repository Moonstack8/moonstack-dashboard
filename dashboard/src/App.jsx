import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ClerkProvider, SignedIn, SignedOut, SignIn, useAuth } from '@clerk/clerk-react'
import { ThemeProvider } from './lib/theme'
import { setTokenGetter } from './lib/api'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import AccountView from './pages/AccountView'
import CampaignView from './pages/CampaignView'
import AdSetView from './pages/AdSetView'
import CampaignBuilder from './pages/CampaignBuilder'
import AdView from './pages/AdView'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Wires Clerk's getToken into the axios client
function AuthSetup() {
  const { getToken } = useAuth()
  useEffect(() => { setTokenGetter(getToken) }, [getToken])
  return null
}

export default function App() {
  return (
    <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY}>
      <ThemeProvider>
        <SignedOut>
          <div className="min-h-screen flex items-center justify-center bg-[rgb(var(--bg-base))]">
            <SignIn />
          </div>
        </SignedOut>

        <SignedIn>
          <AuthSetup />
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
                    <Route path="/ads/:adId" element={<AdView />} />
                    <Route path="/builder" element={<CampaignBuilder />} />
                  </Routes>
                </main>
              </div>
            </BrowserRouter>
          </QueryClientProvider>
        </SignedIn>
      </ThemeProvider>
    </ClerkProvider>
  )
}
