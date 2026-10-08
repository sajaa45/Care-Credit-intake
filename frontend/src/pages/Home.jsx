import { Link } from "react-router-dom";

const ROLES = [
  { to: "/applicant", title: "Applicant", text: "Apply for financing of a medical treatment." },
  { to: "/employee", title: "Employee", text: "Review applications and record decisions." },
  { to: "/compliance", title: "Compliance", text: "Inspect records and manage retention." },
];

export default function Home() {
  return (
    <>
      <h1>Care Credit intake</h1>
      <p className="lede">Choose who you are to continue.</p>
      <div className="roles">
        {ROLES.map((role) => (
          <Link key={role.to} to={role.to} className="role">
            <span className="role-title">{role.title}</span>
            <span className="role-text">{role.text}</span>
          </Link>
        ))}
      </div>
    </>
  );
}
