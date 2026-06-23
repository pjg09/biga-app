import { Routes, Route, Navigate } from 'react-router-dom';
import LandingPage      from './pages/LandingPage';
import LoginPage        from './pages/LoginPage';
import TeacherDashboard from './pages/TeacherDashboard';
import PAEDashboard     from './pages/PAEDashboard';
import ProtectedRoute   from './components/ProtectedRoute';

export default function App() {
  return (
    <Routes>
      <Route path="/"       element={<LandingPage />} />
      <Route path="/login"  element={<LoginPage />} />

      <Route
        path="/dashboard/teacher"
        element={
          <ProtectedRoute allowedRoles={['TEACHER']}>
            <TeacherDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/pae"
        element={
          <ProtectedRoute allowedRoles={['PAE_OPERATOR']}>
            <PAEDashboard />
          </ProtectedRoute>
        }
      />

      {/* Redirige /dashboard al dashboard correcto según rol */}
      <Route path="/dashboard" element={<DashboardRedirect />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function DashboardRedirect() {
  const user = JSON.parse(localStorage.getItem('user') || 'null');
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === 'PAE_OPERATOR' ? '/dashboard/pae' : '/dashboard/teacher'} replace />;
}
