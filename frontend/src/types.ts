export type Direction = 'N' | 'S' | 'E' | 'W'
export type SignalColor = 'RED' | 'YELLOW' | 'GREEN'
export type Phase = 'NS_GREEN' | 'NS_YELLOW' | 'EW_GREEN' | 'EW_YELLOW' | 'ALL_RED'

export interface ApproachState {
  vehicles: number
  queue: number
  weighted_vehicles: number
  demand: number
  waiting_seconds: number
}

export interface SystemState {
  type: 'traffic_state'
  timestamp: string
  running: boolean
  ai_running: boolean
  ai_mode: string
  phase: Phase
  next_phase: Phase
  remaining: number
  phase_duration: number
  signals: Record<Direction, SignalColor>
  traffic: Record<Direction, ApproachState>
  esp32: {
    mode: 'mock' | 'serial'
    connected: boolean
    last_ack: string | null
    last_error: string | null
  }
  fps: number
  cycle: number
}

