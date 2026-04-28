export { api } from './client'

// ── Types ─────────────────────────────────────────────────────────────────────
export interface Driver   { id: number; name: string; notes: string; created_at: string }
export interface Kart     { id: number; name: string; motor_type: string; battery_type: string; mass_kg: number; notes: string; settings_json?: string; gear_json?: string }
export interface Track    { id: number; name: string; length_m: number | null; lat_center: number | null; lon_center: number | null }

export interface Session {
  id: number; driver_id: number; kart_id: number; track_id: number
  driver_name: string; kart_name: string; track_name: string
  date: string; session_type: string; notes: string
  lap_count: number; best_lap_s: number | null; created_at: string
}

export interface Lap      { id: number; session_id: number; lap_number: number; lap_time_s: number; is_valid: boolean; created_at?: string; recorded_at?: string }
export interface Job      { id: number; type: string; status: string; priority: number; created_at: string; updated_at: string; result_json?: string; error_msg?: string }
export interface User     { id: number; username: string; display_name: string; role: string; created_at: string }

export interface Telemetry {
  lap_id: number
  time: number[]
  speed_ms: number[]
  lat?: number[] | null
  lon?: number[] | null
  phase?: string[] | null
  has_gps: boolean
  lateral_acc?: number[] | null
  inline_acc?:  number[] | null
  yaw_rate?:    number[] | null
}

export interface EnergyResult {
  lap_id: number
  total_kwh: number
  regen_kwh: number
  net_kwh: number
  avg_power_kw: number
  peak_power_kw: number
  estimated_range_km: number
  laps_per_charge: number
}

export interface SectorOut {
  sector_num: number
  dist_start_m: number
  dist_end_m: number
  time_s: number
  avg_speed_kmh: number
  min_speed_kmh: number
  max_speed_kmh: number
}

export interface CornerOut {
  corner_index: number
  entry_speed_kmh: number
  apex_speed_kmh: number
  exit_speed_kmh: number
  entry_time_s: number
  apex_time_s: number
}

export interface SmoothnessResult {
  lap_id: number
  smoothness_score: number
}

export interface FeatureVector {
  lap_id: number
  driver_id: number
  throttle_variance: number
  braking_intensity: number
  corner_entry_speed_avg: number
  accel_consistency: number
  smoothness_score: number
}

export interface DeltaPoint { distance_m: number; delta_s: number }
export interface CompareResult {
  lap_a_id: number; lap_b_id: number
  delta_points: DeltaPoint[]
  lap_a_time_s: number; lap_b_time_s: number
}

export interface DriverStyle {
  driver_id: number; style_label: string; confidence: number; sessions_analyzed: number; updated_at: string
}

export interface Recommendation {
  category: string
  setting_key: string
  current_value: string | number
  recommended_value: string | number
  delta: string | number | null
  reason: string
  predicted_outcome: string
  priority: number
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
