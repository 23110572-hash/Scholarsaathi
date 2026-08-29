import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { EligibilityAssistant } from './components/EligibilityAssistant'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AssistantProvider } from './context/AssistantContext'
import { AuthProvider } from './context/AuthContext'
import { ApplicationPage } from './pages/ApplicationPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { OrganizationDashboard } from './pages/OrganizationDashboard'
import { ProviderPage } from './pages/ProviderPage'
import { ScholarshipCatalogPage } from './pages/ScholarshipCatalogPage'
import { ScholarshipDetailPage } from './pages/ScholarshipDetailPage'
import { StudentApplicationsPage } from './pages/StudentApplicationsPage'
import { StudentDashboard } from './pages/StudentDashboard'
import { StudentProfilePage } from './pages/StudentProfilePage'
import { StudentSavedPage } from './pages/StudentSavedPage'

function NotFound() {
  return (
    <main className="screen-center">
      <p className="section-kicker">404</p>
      <h1>This page is not part of the journey.</h1>
      <Link className="button button-primary" to="/scholarships">Browse scholarships</Link>
    </main>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AssistantProvider>
        <Layout>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/scholarships" element={<ScholarshipCatalogPage />} />
          <Route path="/providers" element={<ProviderPage />} />
          <Route path="/login/:realm" element={<LoginPage />} />
          <Route
            path="/student"
            element={<ProtectedRoute realm="STUDENT"><StudentDashboard /></ProtectedRoute>}
          />
          <Route
            path="/student/applications"
            element={<ProtectedRoute realm="STUDENT"><StudentApplicationsPage /></ProtectedRoute>}
          />
          <Route
            path="/student/profile"
            element={<ProtectedRoute realm="STUDENT"><StudentProfilePage /></ProtectedRoute>}
          />
          <Route
            path="/student/saved"
            element={<ProtectedRoute realm="STUDENT"><StudentSavedPage /></ProtectedRoute>}
          />
          <Route path="/scholarships/:scholarshipId" element={<ScholarshipDetailPage />} />
          <Route
            path="/applications/:applicationId"
            element={<ProtectedRoute realm="STUDENT"><ApplicationPage /></ProtectedRoute>}
          />
          <Route
            path="/organization"
            element={<ProtectedRoute realm="ORGANIZATION_MEMBER"><OrganizationDashboard /></ProtectedRoute>}
          />
          <Route path="/login" element={<Navigate to="/login/student" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        <EligibilityAssistant />
        </Layout>
      </AssistantProvider>
    </AuthProvider>
  )
}
