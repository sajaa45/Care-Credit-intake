import { Link } from "react-router-dom";

export default function ComingSoon({ title }) {
  return (
    <>
      <h1>{title}</h1>
      <p className="lede">This part isn't built yet.</p>
      <Link to="/" className="button secondary">Back to start</Link>
    </>
  );
}
