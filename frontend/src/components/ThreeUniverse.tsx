import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GraphData, GraphNode } from '../types';

interface ThreeUniverseProps {
  graphData: GraphData | null;
  selectedNodeId?: string | null;
  onSelectNode?: (node: GraphNode) => void;
  className?: string;
  interactive?: boolean;
}

export const ThreeUniverse: React.FC<ThreeUniverseProps> = ({
  graphData,
  selectedNodeId,
  onSelectNode,
  className = 'w-full h-full',
  interactive = true,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const resetCameraRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // 1. Scene Setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x121924, 0.02);

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || (window.innerHeight - 65);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    const defaultCameraZ = 28;
    camera.position.set(0, 0, defaultCameraZ);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 2. Lighting with Palette (#9DB2BF and #DDE6ED)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const keyLight = new THREE.PointLight(0xdde6ed, 3.2, 90);
    keyLight.position.set(10, 15, 20);
    scene.add(keyLight);

    const fillLight = new THREE.PointLight(0x9db2bf, 2.5, 90);
    fillLight.position.set(-20, -10, -15);
    scene.add(fillLight);

    // 3. Ambient Star Field / Vector Particles
    const starCount = 1200;
    const starGeometry = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    const starColors = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount; i++) {
      starPositions[i * 3] = (Math.random() - 0.5) * 90;
      starPositions[i * 3 + 1] = (Math.random() - 0.5) * 90;
      starPositions[i * 3 + 2] = (Math.random() - 0.5) * 90;

      const rand = Math.random();
      if (rand < 0.45) {
        // #9DB2BF (rgb: 157, 178, 191)
        starColors[i * 3] = 0.61;
        starColors[i * 3 + 1] = 0.70;
        starColors[i * 3 + 2] = 0.75;
      } else if (rand < 0.75) {
        // #DDE6ED (rgb: 221, 230, 237)
        starColors[i * 3] = 0.87;
        starColors[i * 3 + 1] = 0.90;
        starColors[i * 3 + 2] = 0.93;
      } else {
        // #526D82 (rgb: 82, 109, 130)
        starColors[i * 3] = 0.32;
        starColors[i * 3 + 1] = 0.43;
        starColors[i * 3 + 2] = 0.51;
      }
    }

    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    starGeometry.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

    const starMaterial = new THREE.PointsMaterial({
      size: 0.16,
      vertexColors: true,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });
    const starField = new THREE.Points(starGeometry, starMaterial);
    scene.add(starField);

    // 4. Graph Visual Elements (Nodes & Links)
    const universeRoot = new THREE.Group();
    universeRoot.position.set(0, 0, 0);
    scene.add(universeRoot);

    const nodeMeshes: Map<string, THREE.Mesh> = new Map();
    const nodeDataMap: Map<string, GraphNode> = new Map();
    const interactiveObjects: THREE.Object3D[] = [];

    const nodesGroup = new THREE.Group();
    const linksGroup = new THREE.Group();
    universeRoot.add(linksGroup);
    universeRoot.add(nodesGroup);

    if (graphData && graphData.nodes.length > 0) {
      // Calculate center offset so all nodes are balanced exactly at (0, 0, 0)
      let minX = Infinity, maxX = -Infinity;
      let minY = Infinity, maxY = -Infinity;
      let minZ = Infinity, maxZ = -Infinity;

      graphData.nodes.forEach((node) => {
        if (node.x < minX) minX = node.x;
        if (node.x > maxX) maxX = node.x;
        if (node.y < minY) minY = node.y;
        if (node.y > maxY) maxY = node.y;
        if (node.z < minZ) minZ = node.z;
        if (node.z > maxZ) maxZ = node.z;
      });

      const centerX = (minX + maxX) / 2 || 0;
      const centerY = (minY + maxY) / 2 || 0;
      const centerZ = (minZ + maxZ) / 2 || 0;

      // Create Nodes using Palette Colors
      graphData.nodes.forEach((node) => {
        let radius = 0.45;
        let colorHex = 0x526d82; // Default chunk: #526D82

        if (node.type === 'document') {
          radius = 1.15;
          colorHex = 0x9db2bf; // Document cluster: #9DB2BF
        } else if (node.type === 'query') {
          radius = 1.45;
          colorHex = 0xdde6ed; // Query node: #DDE6ED
        } else if (node.is_retrieved) {
          radius = 0.85;
          colorHex = 0xdde6ed; // Retrieved evidence: #DDE6ED
        }

        const sphereGeo = new THREE.SphereGeometry(radius, 24, 24);
        const sphereMat = new THREE.MeshStandardMaterial({
          color: colorHex,
          emissive: colorHex,
          emissiveIntensity: node.type === 'query' || node.is_retrieved ? 0.65 : 0.25,
          roughness: 0.2,
          metalness: 0.75,
        });

        const mesh = new THREE.Mesh(sphereGeo, sphereMat);
        mesh.position.set(node.x - centerX, node.y - centerY, node.z - centerZ);
        mesh.userData = { node };

        // Outer glow wireframe ring
        if (node.type === 'query' || node.type === 'document' || node.is_retrieved) {
          const ringGeo = new THREE.RingGeometry(radius * 1.3, radius * 1.48, 32);
          const ringMat = new THREE.MeshBasicMaterial({
            color: colorHex,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.45,
          });
          const ring = new THREE.Mesh(ringGeo, ringMat);
          ring.rotation.x = Math.PI / 2;
          mesh.add(ring);
        }

        nodesGroup.add(mesh);
        nodeMeshes.set(node.id, mesh);
        nodeDataMap.set(node.id, node);
        interactiveObjects.push(mesh);
      });

      // Create Links
      graphData.links.forEach((link) => {
        const sourceNode = nodeDataMap.get(link.source);
        const targetNode = nodeDataMap.get(link.target);
        if (!sourceNode || !targetNode) return;

        const points = [
          new THREE.Vector3(sourceNode.x - centerX, sourceNode.y - centerY, sourceNode.z - centerZ),
          new THREE.Vector3(targetNode.x - centerX, targetNode.y - centerY, targetNode.z - centerZ),
        ];
        const lineGeo = new THREE.BufferGeometry().setFromPoints(points);

        const isRay = link.type === 'retrieval_ray';
        const lineMat = new THREE.LineBasicMaterial({
          color: isRay ? 0xdde6ed : 0x9db2bf,
          transparent: true,
          opacity: isRay ? 0.9 : 0.25,
          linewidth: isRay ? 2 : 1,
        });

        const line = new THREE.Line(lineGeo, lineMat);
        linksGroup.add(line);
      });
    } else {
      // Default idle floating universe when no articles loaded yet - centered around (0,0,0)
      const demoClusterCount = 4;
      for (let c = 0; c < demoClusterCount; c++) {
        const angle = (2 * Math.PI * c) / demoClusterCount;
        const cx = 7.5 * Math.cos(angle);
        const cz = 7.5 * Math.sin(angle);

        const parentGeo = new THREE.SphereGeometry(0.95, 20, 20);
        const parentMat = new THREE.MeshStandardMaterial({
          color: 0x9db2bf,
          emissive: 0x27374d,
          emissiveIntensity: 0.4,
          roughness: 0.2,
          metalness: 0.8,
        });
        const parentMesh = new THREE.Mesh(parentGeo, parentMat);
        parentMesh.position.set(cx, 0, cz);
        nodesGroup.add(parentMesh);

        for (let j = 0; j < 6; j++) {
          const subAngle = (2 * Math.PI * j) / 6;
          const subGeo = new THREE.SphereGeometry(0.38, 16, 16);
          const isHighlight = j % 3 === 0;
          const subMat = new THREE.MeshStandardMaterial({
            color: isHighlight ? 0xdde6ed : 0x526d82,
            emissive: isHighlight ? 0x9db2bf : 0x27374d,
            emissiveIntensity: isHighlight ? 0.45 : 0.2,
          });
          const subMesh = new THREE.Mesh(subGeo, subMat);
          subMesh.position.set(cx + 2.2 * Math.cos(subAngle), Math.sin(j) * 1.1, cz + 2.2 * Math.sin(subAngle));
          nodesGroup.add(subMesh);
        }
      }
    }

    // 5. Interaction (Orbit / Raycasting)
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let rotationSpeedY = 0.0008;

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2(-999, -999);

    const onMouseDown = (e: MouseEvent) => {
      if (!interactive) return;
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onMouseMove = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      if (isDragging && interactive) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        universeRoot.rotation.y += deltaX * 0.006;
        universeRoot.rotation.x = Math.max(-Math.PI / 3, Math.min(Math.PI / 3, universeRoot.rotation.x + deltaY * 0.006));
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;
      }
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      if (!interactive) return;
      e.preventDefault();
      camera.position.z = Math.max(12, Math.min(50, camera.position.z + e.deltaY * 0.025));
      camera.lookAt(0, 0, 0);
    };

    const onClick = () => {
      if (!interactive) return;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects);
      if (intersects.length > 0) {
        const hitNode = intersects[0].object.userData?.node as GraphNode;
        if (hitNode && onSelectNode) {
          onSelectNode(hitNode);
        }
      }
    };

    const dom = renderer.domElement;
    dom.style.width = '100%';
    dom.style.height = '100%';
    dom.style.display = 'block';

    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });
    dom.addEventListener('click', onClick);

    resetCameraRef.current = () => {
      camera.position.set(0, 0, defaultCameraZ);
      camera.lookAt(0, 0, 0);
      universeRoot.rotation.set(0, 0, 0);
    };

    // 6. Animation Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Continuous universe drift around exact center
      if (!isDragging) {
        universeRoot.rotation.y += rotationSpeedY * 0.4;
      }
      starField.rotation.y -= 0.0003;

      // Pulse query node if present
      const queryMesh = nodeMeshes.get('node_active_query');
      if (queryMesh) {
        const pulse = 1 + Math.sin(elapsed * 4) * 0.15;
        queryMesh.scale.set(pulse, pulse, pulse);
      }

      // Raycasting hover check
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects);
      if (intersects.length > 0) {
        const targetNode = intersects[0].object.userData?.node as GraphNode;
        setHoveredNode(targetNode || null);
        dom.style.cursor = 'pointer';
      } else {
        setHoveredNode(null);
        dom.style.cursor = isDragging ? 'grabbing' : 'grab';
      }

      renderer.render(scene, camera);
    };

    animate();

    // 7. Dynamic Resize Handler with ResizeObserver
    const updateSize = () => {
      if (!container) return;
      const w = container.clientWidth || window.innerWidth;
      const h = container.clientHeight || (window.innerHeight - 65);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      camera.lookAt(0, 0, 0);
      renderer.setSize(w, h);
    };

    const resizeObserver = new ResizeObserver(() => {
      updateSize();
    });
    resizeObserver.observe(container);
    window.addEventListener('resize', updateSize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      dom.removeEventListener('click', onClick);
      window.removeEventListener('resize', updateSize);
      renderer.dispose();
      starGeometry.dispose();
      starMaterial.dispose();
      container.innerHTML = '';
    };
  }, [graphData, interactive, onSelectNode]);

  return (
    <div className={`relative ${className} overflow-hidden select-none`}>
      <div ref={mountRef} className="absolute inset-0 w-full h-full block" />

      {/* Hover Tooltip HUD */}
      {hoveredNode && (
        <div className="absolute bottom-6 left-6 pointer-events-none glass-panel-glow p-4 rounded-xl max-w-sm border border-[#9DB2BF]/40 text-xs shadow-2xl backdrop-blur-md bg-[#27374D]/90">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="w-2.5 h-2.5 rounded-full animate-ping"
              style={{ backgroundColor: hoveredNode.color }}
            />
            <span className="font-semibold text-slate-200 uppercase tracking-wider text-[10px]">
              {hoveredNode.type} Node
            </span>
            {hoveredNode.is_retrieved && (
              <span className="ml-auto bg-[#DDE6ED]/20 text-[#DDE6ED] px-1.5 py-0.5 rounded text-[10px] font-bold border border-[#DDE6ED]/30">
                Retrieved Evidence
              </span>
            )}
          </div>
          <div className="font-bold text-sm text-white mb-1 line-clamp-1">{hoveredNode.name}</div>
          {hoveredNode.section && (
            <div className="text-slate-300 mb-1">Section: {hoveredNode.section}</div>
          )}
          {hoveredNode.preview && (
            <div className="text-slate-300 italic line-clamp-2">"{hoveredNode.preview}"</div>
          )}
          <div className="text-[10px] text-[#9DB2BF] font-medium mt-2">Click node to inspect full context in Evidence Panel</div>
        </div>
      )}

      {/* Orbit Navigation Guide Badge & Recenter Button */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        <button
          onClick={() => resetCameraRef.current?.()}
          className="glass-panel px-3 py-1.5 rounded-lg text-[11px] text-[#DDE6ED] hover:text-white hover:border-[#DDE6ED]/60 border border-[#9DB2BF]/20 transition-all shadow-md active:scale-95 flex items-center gap-1.5 cursor-pointer bg-[#27374D]/80"
          title="Reset 3D camera to exact center"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#DDE6ED]"></span>
          <span>Recenter View</span>
        </button>
        <div className="pointer-events-none glass-panel px-3 py-1.5 rounded-lg text-[11px] text-slate-300 flex items-center gap-2 border border-[#9DB2BF]/20 bg-[#27374D]/70">
          <span className="w-1.5 h-1.5 rounded-full bg-[#9DB2BF] animate-pulse"></span>
          <span>Drag: Rotate · Scroll: Zoom · Click: Inspect</span>
        </div>
      </div>
    </div>
  );
};
