import { HashRouter as Router, Routes, Route, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useAuthStore } from '@/stores/state'
import { navigationService } from '@/services/navigation'
import { getAuthStatus } from '@/api/lightrag'
import { Toaster } from 'sonner'
import App from './App'
import LoginPage from '@/features/LoginPage'
import ThemeProvider from '@/components/ThemeProvider'

const AppContent = () => {
  const [initializing, setInitializing] = useState(true)
  const { isAuthenticated } = useAuthStore()
  const navigate = useNavigate()

  // Set navigate function for navigation service
  useEffect(() => {
    navigationService.setNavigate(navigate)
  }, [navigate])

  // Token validity and auth config check
  useEffect(() => {

    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('LIGHTRAG-API-TOKEN')

        if (token && isAuthenticated) {
          setInitializing(false);
          return;
        }

        // If no token, check if auth is disabled on backend
        if (!token) {
          try {
            const authStatus = await getAuthStatus()
            
            // If auth is not configured, auto-login as guest
            if (!authStatus.auth_configured && authStatus.access_token) {
              useAuthStore.getState().login(
                authStatus.access_token, 
                true, // guest mode
                authStatus.core_version,
                authStatus.api_version,
                authStatus.webui_title || null,
                authStatus.webui_description || null
              )
              setInitializing(false)
              return
            }
          } catch (authError) {
            console.error('Failed to check auth status:', authError)
            // If we can't check auth status, assume auth is required
          }
          
          // Auth is required, clear any existing auth state
          useAuthStore.getState().logout()
        }
      } catch (error) {
        console.error('Auth initialization error:', error)
        if (!isAuthenticated) {
          useAuthStore.getState().logout()
        }
      } finally {
        setInitializing(false)
      }
    }

    checkAuth()

    return () => {
    }
  }, [isAuthenticated])

  // Redirect effect for protected routes
  useEffect(() => {
    if (!initializing && !isAuthenticated) {
      const currentPath = window.location.hash.slice(1);
      if (currentPath !== '/login') {
        console.log('Not authenticated, redirecting to login');
        navigate('/login');
      }
    }
  }, [initializing, isAuthenticated, navigate]);

  // Show nothing while initializing
  if (initializing) {
    return null
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={isAuthenticated ? <App /> : null}
      />
    </Routes>
  )
}

const AppRouter = () => {
  return (
    <ThemeProvider>
      <Router>
        <AppContent />
        <Toaster
          position="bottom-center"
          theme="system"
          closeButton
          richColors
        />
      </Router>
    </ThemeProvider>
  )
}

export default AppRouter
