import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { PatientApp } from './patient/PatientApp.tsx'

// Path-based split, not a router dependency: the clinician console stays at
// "/" exactly as it was; the patient-facing app (further work, simulated
// patients only) lives at "/patient" as a separate shell.
const Root = window.location.pathname.startsWith('/patient') ? PatientApp : App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
