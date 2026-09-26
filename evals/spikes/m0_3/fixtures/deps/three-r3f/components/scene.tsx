"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Environment } from "@react-three/drei";
import { useRef } from "react";
import type { Mesh } from "three";

function Box() {
  const mesh = useRef<Mesh>(null);
  useFrame((_, delta) => {
    if (mesh.current) mesh.current.rotation.y += delta;
  });
  return (
    <mesh ref={mesh}>
      <boxGeometry args={[1.5, 1.5, 1.5]} />
      <meshStandardMaterial color="#ff5a1f" />
    </mesh>
  );
}

export default function Scene() {
  return (
    <Canvas camera={{ position: [3, 3, 3] }} gl={{ preserveDrawingBuffer: true }} data-testid="probe">
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} />
      <Box />
      <OrbitControls />
      <Environment preset="city" />
    </Canvas>
  );
}
