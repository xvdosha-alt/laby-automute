import { Float, OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import "./CloudTab.css";

function CloudCube({ position, color, label }) {
  const ref = useRef();
  useFrame((_, delta) => {
    if (ref.current) {
      ref.current.rotation.x += delta * 0.3;
      ref.current.rotation.y += delta * 0.5;
    }
  });

  return (
    <Float speed={2} rotationIntensity={0.4} floatIntensity={0.8}>
      <mesh ref={ref} position={position}>
        <boxGeometry args={[0.7, 0.7, 0.7]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.35}
          metalness={0.6}
          roughness={0.2}
        />
      </mesh>
    </Float>
  );
}

function CloudScene({ mutes }) {
  const cubes = useMemo(() => {
    const colors = ["#38bdf8", "#a78bfa", "#f472b6", "#4ade80", "#fbbf24"];
    const count = Math.min(mutes.length || 1, 24);
    const items = [];
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const radius = 2.5 + (i % 3) * 0.8;
      items.push({
        position: [
          Math.cos(angle) * radius,
          (i % 5) * 0.5 - 1,
          Math.sin(angle) * radius,
        ],
        color: colors[i % colors.length],
      });
    }
    return items;
  }, [mutes.length]);

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.2} color="#38bdf8" />
      <pointLight position={[-8, -4, -6]} intensity={0.8} color="#a78bfa" />
      <Stars radius={80} depth={40} count={3000} factor={3} fade speed={0.5} />
      {cubes.map((c, i) => (
        <CloudCube key={i} position={c.position} color={c.color} />
      ))}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.5, 0]}>
        <planeGeometry args={[20, 20]} />
        <meshStandardMaterial
          color="#0d1424"
          metalness={0.9}
          roughness={0.1}
          transparent
          opacity={0.6}
        />
      </mesh>
      <OrbitControls enableZoom autoRotate autoRotateSpeed={0.4} />
    </>
  );
}

export default function CloudTab({ stats, mutes }) {
  const synced = mutes.filter((m) => m.link).length;
  const local = mutes.length - synced;

  return (
    <div className="cloud-tab">
      <div className="cloud-scene panel">
        <Canvas camera={{ position: [0, 2, 6], fov: 50 }}>
          <fog attach="fog" args={["#070b14", 8, 22]} />
          <CloudScene mutes={mutes} />
        </Canvas>
        <div className="scene-overlay">
          <span>Облако синхронизации</span>
        </div>
      </div>

      <div className="cloud-side">
        <div className="panel cloud-card">
          <div className="panel-title">Синхронизация skr.sh</div>
          <div className="sync-ring">
            <svg viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="50" className="ring-bg" />
              <circle
                cx="60"
                cy="60"
                r="50"
                className="ring-fill"
                strokeDasharray={`${mutes.length ? (synced / mutes.length) * 314 : 0} 314`}
              />
            </svg>
            <div className="sync-center">
              <span className="sync-pct">
                {mutes.length ? Math.round((synced / mutes.length) * 100) : 0}%
              </span>
              <span className="sync-label">в облаке</span>
            </div>
          </div>
          <div className="sync-stats">
            <div>
              <span className="sync-num">{synced}</span>
              <span>загружено</span>
            </div>
            <div>
              <span className="sync-num">{local}</span>
              <span>только локально</span>
            </div>
            <div>
              <span className="sync-num">{stats?.total ?? 0}</span>
              <span>всего записей</span>
            </div>
          </div>
        </div>

        <div className="panel cloud-card cloud-recent">
          <div className="panel-title">Последние в облаке</div>
          <ul>
            {mutes
              .filter((m) => m.link)
              .slice(0, 8)
              .map((m) => (
                <li key={m.id}>
                  <span className="cloud-nick">{m.nickname}</span>
                  <a href={m.link} target="_blank" rel="noreferrer">
                    открыть
                  </a>
                </li>
              ))}
            {!mutes.some((m) => m.link) && (
              <li className="empty-inline">Загрузок пока нет</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
