export default function ReceivedCard({ applicationNumber, receivedAt }) {
  return (
    <section className="received" role="status">
      <div className="received-icon" aria-hidden="true">✓</div>
      <h1>We've received your application</h1>
      <p className="lede">Thank you. Your application has been submitted successfully.</p>
      <dl className="summary">
        <dt>Application</dt>
        <dd>Number {applicationNumber} under your ID number</dd>
        <dt>Received</dt>
        <dd>{new Date(receivedAt).toLocaleString("en-GB")}</dd>
      </dl>
    </section>
  );
}
