// Unit conversions — all internal data is stored in SI (m/s, kg, m, °C)
// Display in US customary units throughout the UI

export const mph   = (ms:  number) => ms  * 2.23694
export const mphKmh = (kmh: number) => kmh * 0.621371
export const lbs   = (kg:  number) => kg  * 2.20462
export const fahr  = (c:   number) => c   * 9/5 + 32
export const feet  = (m:   number) => m   * 3.28084
export const miles = (m:   number) => m   * 0.000621371

export const fmtMph    = (ms:  number, dp = 1) => `${mph(ms).toFixed(dp)} mph`
export const fmtMphKmh = (kmh: number, dp = 1) => `${mphKmh(kmh).toFixed(dp)} mph`
export const fmtLbs    = (kg:  number, dp = 1) => `${lbs(kg).toFixed(dp)} lbs`
export const fmtFahr   = (c:   number, dp = 1) => `${fahr(c).toFixed(dp)}°F`
export const fmtFeet   = (m:   number, dp = 0) => `${feet(m).toFixed(dp)} ft`
export const fmtMiles  = (m:   number, dp = 2) => `${miles(m).toFixed(dp)} mi`

export const fmtLap = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return `${m}:${sec}`
}
