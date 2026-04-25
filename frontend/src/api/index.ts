export { api } from './client'

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Driver   { id: number; name: string; notes: string; created_at: string }
export interface Kart     { id: number; name: string; motor_type: string; battery_type: string; mass_kg: number; notes: string }
export interface Track    { id: number; name: string; length_m: number | null; lat_center: number | null; lon_center: number | null }
export interface Session  { id: number; driver_id: number; kart_id: number; track_id: number; date: string; session_type: string; notes: string }
export interface Lap      { id: number; session_id: number; lap_number: number; lap_time_s: number; is_valid: boolean }
export interface Job      { id: number; type: string; status: string; priority: number; created_at: string; updated_at: string; result_json?: string; error_msg?: string }
export interface User     { id: number; username: string; display_name: string; role: string; created_at: string }

export interface Telemetry {
  time: number[]; speed: number[]; lat?: number[]; lon?: number[]; phase?: string[]
}

export interface DriverStyle {
  driver_id: number; style_label: string; confidence: number; sessions_analyzed: number; updated_at: string
}

export interface SystemStatus {
  status: string; first_boot: boolean; version: string; pi_mode: boolean
  stats: { users: number; sessions: number; drivers: number; pending_jobs: number }
  storage: { used_pct: number; status: string }
}

export interface ComplianceItem {
  rule_name: string; rule_section: string; status: string
  current_value: string; limit_value: string; message: string; actionable: string
}
export interface ComplianceResult {
  passed: boolean
  items: ComplianceItem[]
}
