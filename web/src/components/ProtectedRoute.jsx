import { Navigate } from 'react-router-dom';

export default function ProtectedRoute({ children, allowedRoles }) {
  const token = localStorage.getItem('token');
  const user  = JSON.parse(localStorage.getItem('user') || 'null');

  if (!token || !user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    const home = { ADMIN: '/dashboard/admin', PAE_OPERATOR: '/dashboard/pae', TEACHER: '/dashboard/teacher' };
    return <Navigate to={home[user.role] ?? '/dashboard/teacher'} replace />;
  }

  return children;
}
