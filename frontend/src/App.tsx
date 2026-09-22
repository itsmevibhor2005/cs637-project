import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Cpu,
  Pause,
  Play,
  Radio,
  Route,
  Timer,
  Wifi,
  WifiOff,
} from "lucide-react";
import type {
  ApproachState,
  Direction,
  Phase,
  SignalColor,
  SystemState,
} from "./types";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS = API.replace(/^http/, "ws") + "/ws/live";
const directions: Direction[] = ["N", "E", "S", "W"];
const labels: Record<Direction, string> = {
  N: "North",
  S: "South",
  E: "East",
  W: "West",
};
const emptyTraffic: ApproachState = {
  vehicles: 0,
  queue: 0,
  weighted_vehicles: 0,
  demand: 0,
  waiting_seconds: 0,
};

function StatusPill({
  ok,
  children,
}: {
  ok: boolean;
  children: React.ReactNode;
}) {
  return (
    <span className={`status-pill ${ok ? "ok" : "off"}`}>
      <i />
      {children}
    </span>
  );
}

function TrafficLight({ color }: { color: SignalColor }) {
  return (
    <div className="traffic-light" aria-label={`${color} signal`}>
      {(["RED", "YELLOW", "GREEN"] as SignalColor[]).map((c) => (
        <span
          key={c}
          className={`${c.toLowerCase()} ${color === c ? "active" : ""}`}
        />
      ))}
    </div>
  );
}

function ApproachCard({
  direction,
  data,
  signal,
}: {
  direction: Direction;
  data: ApproachState;
  signal: SignalColor;
}) {
  return (
    <article className={`approach approach-${direction.toLowerCase()}`}>
      <div className="approach-title">
        <span>{direction}</span>
        <div>
          <strong>{labels[direction]}</strong>
          <small>Approach</small>
        </div>
      </div>
      <TrafficLight color={signal} />
      <div className="approach-stats">
        <div>
          <b>{data.vehicles}</b>
          <small>Vehicles</small>
        </div>
        <div>
          <b>{data.queue}</b>
          <small>In queue</small>
        </div>
        <div>
          <b>{Math.round(data.demand)}</b>
          <small>Demand</small>
        </div>
      </div>
      <div className="demand-track">
        <span style={{ width: `${Math.min(100, data.demand * 2.2)}%` }} />
      </div>
    </article>
  );
}

function Metric({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: string | number;
  label: string;
}) {
  return (
    <div className="metric">
      <span>{icon}</span>
      <div>
        <strong>{value}</strong>
        <small>{label}</small>
      </div>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState<SystemState | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retry = useRef<number | undefined>(undefined);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let disposed = false;
    const connect = () => {
      socket = new WebSocket(WS);
      socket.onopen = () => {
        setConnected(true);
        setError(null);
        socket?.send("hello");
      };
      socket.onmessage = (event) => setState(JSON.parse(event.data));
      socket.onerror = () => setError("Live connection interrupted");
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) retry.current = window.setTimeout(connect, 1500);
      };
    };
    fetch(`${API}/api/system`)
      .then((r) => r.json())
      .then(setState)
      .catch(() => setError("Backend is offline"));
    connect();
    return () => {
      disposed = true;
      clearTimeout(retry.current);
      socket?.close();
    };
  }, []);

  const command = async (path: string, body?: object) => {
    try {
      const response = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok)
        throw new Error((await response.json()).detail || "Command failed");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Command failed");
    }
  };

  const totalVehicles = useMemo(
    () =>
      state ? directions.reduce((n, d) => n + state.traffic[d].vehicles, 0) : 0,
    [state],
  );
  const phaseProgress = state?.phase_duration
    ? ((state.phase_duration - state.remaining) / state.phase_duration) * 100
    : 0;
  const fallbackSignals: Record<Direction, SignalColor> = {
    N: "RED",
    S: "RED",
    E: "RED",
    W: "RED",
  };
  const signals = state?.signals || fallbackSignals;
  const traffic = state?.traffic || {
    N: emptyTraffic,
    S: emptyTraffic,
    E: emptyTraffic,
    W: emptyTraffic,
  };

  return (
    <main className="shell">
      <header>
        <div className="brand">
          <span className="brand-mark">
            <Route />
          </span>
          <div>
            <p>
              FLOW<span>SYNC</span>
            </p>
            <small>Adaptive intersection control</small>
          </div>
        </div>
        <div className="header-status">
          <StatusPill ok={connected}>
            {connected ? "Live data" : "Reconnecting"}
          </StatusPill>
          <StatusPill ok={!!state?.esp32.connected}>
            {state?.esp32.connected
              ? `ESP32 ${state.esp32.mode}`
              : "ESP32 offline"}
          </StatusPill>
        </div>
      </header>

      {error && (
        <div className="alert">
          <AlertTriangle size={17} />
          {error}
        </div>
      )}

      <section className="hero-grid">
        <div className="phase-panel panel">
          <div className="eyebrow">
            <Radio size={14} /> Live controller
          </div>
          <div className="phase-main">
            <div>
              <small>Active phase</small>
              <h1>{(state?.phase || "ALL_RED").replace("_", " ")}</h1>
            </div>
            <div className="countdown">
              {state?.remaining ?? 0}
              <small>SEC</small>
            </div>
          </div>
          <div className="progress">
            <span style={{ width: `${phaseProgress}%` }} />
          </div>
          <div className="phase-meta">
            <span>
              Next <b>{state?.next_phase.replaceAll("_", " ") || "N GREEN"}</b>
            </span>
            <span>
              Completed phases <b>#{state?.cycle ?? 0}</b>
            </span>
          </div>
          <div className="controls">
            <button
              className="primary"
              onClick={() =>
                command(
                  state?.running ? "/api/system/stop" : "/api/system/start",
                )
              }
            >
              {state?.running ? (
                <>
                  <Pause size={17} /> Safe stop
                </>
              ) : (
                <>
                  <Play size={17} /> Start system
                </>
              )}
            </button>
            {directions.map((direction) => (
              <button
                key={direction}
                onClick={() =>
                  command("/api/manual/phase", {
                    phase: `${direction}_GREEN` as Phase,
                    duration: 15,
                  })
                }
              >
                {direction} 15s
              </button>
            ))}
          </div>
        </div>

        <div className="metrics-panel panel">
          <div className="eyebrow">
            <Activity size={14} /> System pulse
          </div>
          <div className="metrics-grid">
            <Metric
              icon={<Bot />}
              value={state?.ai_running ? "Online" : "Idle"}
              label={`AI · ${state?.ai_mode || "mock"}`}
            />
            <Metric
              icon={<Cpu />}
              value={state?.esp32.connected ? "Ready" : "Offline"}
              label="Edge controller"
            />
            <Metric
              icon={<Timer />}
              value={state?.fps ?? 0}
              label="Vision FPS"
            />
            <Metric
              icon={connected ? <Wifi /> : <WifiOff />}
              value={totalVehicles}
              label="Vehicles seen"
            />
          </div>
        </div>
      </section>

      <section className="workspace">
        <div className="intersection-panel panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Junction map</div>
              <h2>Four-way live state</h2>
            </div>
            <span className="legend">
              <i /> active movement
            </span>
          </div>
          <div className="intersection">
            <div className="road vertical" />
            <div className="road horizontal" />
            <div className="junction-core">
              <span>AI</span>
              <small>CONTROL</small>
            </div>
            {directions.map((d) => (
              <ApproachCard
                key={d}
                direction={d}
                data={traffic[d]}
                signal={signals[d]}
              />
            ))}
            <div className="lane lane-v left" />
            <div className="lane lane-v right" />
            <div className="lane lane-h top" />
            <div className="lane lane-h bottom" />
          </div>
        </div>

        <aside className="side-stack">
          <div className="panel demand-panel">
            <div className="eyebrow">Demand matrix</div>
            <h2>Approach pressure</h2>
            {directions.map((d) => (
              <div className="demand-row" key={d}>
                <span>
                  <b>{d}</b>
                  {labels[d]}
                </span>
                <div>
                  <i
                    style={{
                      width: `${Math.min(100, traffic[d].demand * 2.2)}%`,
                    }}
                  />
                </div>
                <strong>{Math.round(traffic[d].demand)}</strong>
              </div>
            ))}
          </div>
          <div className="panel hardware-panel">
            <div className="eyebrow">Hardware link</div>
            <h2>ESP32 telemetry</h2>
            <dl>
              <div>
                <dt>Status</dt>
                <dd className={state?.esp32.connected ? "good" : "bad"}>
                  {state?.esp32.connected ? "Connected" : "Disconnected"}
                </dd>
              </div>
              <div>
                <dt>Transport</dt>
                <dd>{state?.esp32.mode || "—"}</dd>
              </div>
              <div>
                <dt>Last ACK</dt>
                <dd className="mono">{state?.esp32.last_ack || "Waiting…"}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </section>
      <footer>
        <span>Safety state machine enforced</span>
        <span>Green dynamic · Yellow 3s · All-red 1s</span>
      </footer>
    </main>
  );
}
