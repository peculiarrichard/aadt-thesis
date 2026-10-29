import type { DoctorReport as DoctorReportData } from '../api'

export function DoctorReport({ report }: { report: DoctorReportData }) {
  const generated = new Date(report.generatedAt)

  return (
    <div className="doctor-report">
      <div className="doctor-report__header">
        <h4>Consultation Report</h4>
        <span className="doctor-report__meta">
          {generated.toLocaleString()} -- {report.clinicianName}
        </span>
      </div>

      <p className="doctor-report__disclaimer">{report.disclaimer}</p>

      <dl className="doctor-report__clerical">
        <div>
          <dt>Patient reference</dt>
          <dd>{report.patientReference || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Age</dt>
          <dd>{report.patientAge || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Sex</dt>
          <dd>{report.patientSex || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Temperature</dt>
          <dd>{report.temperature || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Blood pressure</dt>
          <dd>{report.bloodPressure || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Pulse rate</dt>
          <dd>{report.pulseRate || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Respiratory rate</dt>
          <dd>{report.respiratoryRate || 'Not recorded'}</dd>
        </div>
        <div>
          <dt>Oxygen saturation</dt>
          <dd>{report.oxygenSaturation || 'Not recorded'}</dd>
        </div>
      </dl>

      <section>
        <h5>Presenting complaint</h5>
        <p>{report.presentingComplaint}</p>
      </section>

      <section>
        <h5>History and clinical impression (AI-suggested)</h5>
        <p>{report.historyAndImpression}</p>
      </section>

      {report.guidelineConsiderations.length > 0 && (
        <section>
          <h5>Guideline-informed considerations</h5>
          <ul>
            {report.guidelineConsiderations.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h5>Assessment</h5>
        <p>{report.assessment}</p>
      </section>

      <section>
        <h5>Plan</h5>
        <p>{report.plan}</p>
      </section>

      <div className="doctor-report__signoff">
        <p>Reviewed and signed by: ______________________________</p>
        <p>{report.clinicianName}</p>
      </div>
    </div>
  )
}
