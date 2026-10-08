import { euro } from "../format.js";

export default function ScheduleTable({ schedule, summary = "Show the full repayment schedule" }) {
  if (!schedule) return null;
  return (
    <details className="schedule">
      <summary>{summary}</summary>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">Opening balance</th>
              <th scope="col">Instalment</th>
              <th scope="col">Interest</th>
              <th scope="col">Repayment</th>
              <th scope="col">Closing balance</th>
            </tr>
          </thead>
          <tbody>
            {schedule.map((row) => (
              <tr key={row.month}>
                <td>{row.month}</td>
                <td>{euro(row.opening_balance)}</td>
                <td>{euro(row.instalment)}</td>
                <td>{euro(row.interest)}</td>
                <td>{euro(row.principal)}</td>
                <td>{euro(row.closing_balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
