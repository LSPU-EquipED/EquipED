import { useAuth } from "@equiped/auth";
import { FacultyHome } from "../components/FacultyHome";

export function FacultyHomePage() {
  const { user } = useAuth();
  return (
    <FacultyHome
      displayName={user?.displayName}
      evaluatorPermissions={user?.evaluatorPermissions}
      userRole={user?.role}
    />
  );
}
