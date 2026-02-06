import React from "react";

import { AUDIT_LOGS } from "../shared/data";

export function HistoryApp() {
  return (
    <section className="page">
      <div className="page-header">
        <h1>History</h1>
        <p>Recent workflow runs and exported artifacts.</p>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>User</th>
              <th>Artifact</th>
              <th>Action</th>
              <th>Destination</th>
              <th>Ticket key</th>
            </tr>
          </thead>
          <tbody>
            {AUDIT_LOGS.map((row) => (
              <tr key={`${row.date}-${row.ticket}`}>
                <td>{row.date}</td>
                <td>{row.user}</td>
                <td>{row.artifact}</td>
                <td>
                  <span className="chip">{row.action}</span>
                </td>
                <td>{row.destination}</td>
                <td>{row.ticket}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
