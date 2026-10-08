import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import Home from "./pages/Home.jsx";
import ApplicantPage from "./pages/ApplicantPage.jsx";
import EmployeePage from "./pages/EmployeePage.jsx";
import CompliancePage from "./pages/CompliancePage.jsx";

const ROLES = [
  { to: "/applicant", label: "Applicant" },
  { to: "/employee", label: "Employee" },
  { to: "/compliance", label: "Compliance" },
];

export default function App() {
  const { pathname } = useLocation();
  const wide = pathname.startsWith("/employee") || pathname.startsWith("/compliance");

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Care Credit</Link>
        <nav className="role-nav" aria-label="Choose a role">
          {ROLES.map((role) => (
            <NavLink key={role.to} to={role.to} className="role-link">
              {role.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className={`page${wide ? " wide" : ""}`}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/applicant" element={<ApplicantPage />} />
          <Route path="/employee" element={<EmployeePage />} />
          <Route path="/compliance" element={<CompliancePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
