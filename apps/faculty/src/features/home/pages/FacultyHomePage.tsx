import { useAuth } from '@equiped/auth';
import { FacultyHome } from '../components/FacultyHome';

export function FacultyHomePage() {
  const { user } = useAuth();

  return <FacultyHome evaluatorPermissions={user?.evaluatorPermissions} />;
}
