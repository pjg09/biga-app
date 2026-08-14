import { Routes, Route, Navigate } from 'react-router-dom';
import LandingPage      from './pages/LandingPage';
import LoginPage        from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import TeacherDashboard from './pages/TeacherDashboard';
import PAEDashboard     from './pages/PAEDashboard';
import AdminDashboard   from './pages/AdminDashboard';
import JustifyPage      from './pages/JustifyPage';
import ProtectedRoute   from './components/ProtectedRoute';

export default function App() {
  return (
    <Routes>
      <Route path="/"       element={<LandingPage />} />
      <Route path="/login"  element={<LoginPage />} />
      <Route path="/recuperar" element={<ForgotPasswordPage />} />
      <Route path="/justificar/:token" element={<JustifyPage />} />

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
      <Route
        path="/dashboard/admin"
        element={
          <ProtectedRoute allowedRoles={['ADMIN']}>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />

      {/* Redirige /dashboard al dashboard correcto según rol */}
      <Route path="/dashboard" element={<DashboardRedirect />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

const DASH_BY_ROLE = {
  ADMIN: '/dashboard/admin',
  PAE_OPERATOR: '/dashboard/pae',
  TEACHER: '/dashboard/teacher',
};

function DashboardRedirect() {
  const user = JSON.parse(localStorage.getItem('user') || 'null');
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={DASH_BY_ROLE[user.role] ?? '/dashboard/teacher'} replace />;
}
