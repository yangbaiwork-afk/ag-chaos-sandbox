// ================= 1. 初始化 Three.js 场景 =================
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// 假资产 A：虚拟番茄 (绿色立方体)
const tomatoGeo = new THREE.BoxGeometry(1, 1, 1);
const tomatoMat = new THREE.MeshBasicMaterial({ color: 0x00C851 });
const tomatoMesh = new THREE.Mesh(tomatoGeo, tomatoMat);
scene.add(tomatoMesh);

// 假资产 B：虚拟机械臂末端 (灰色球体)
const armGeo = new THREE.SphereGeometry(0.5, 16, 16);
const armMat = new THREE.MeshBasicMaterial({ color: 0x888888 });
const armMesh = new THREE.Mesh(armGeo, armMat);
scene.add(armMesh);

camera.position.z = 5;

// ================= 2. 建立 WebSocket 虚实通道 =================
const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    // 同步 3D 空间状态
    armMesh.position.x = data.arm_position[0];
    armMesh.position.y = data.arm_position[1];
    
    // 业务逻辑视觉反馈：受伤变红，安全变绿
    if (data.tomato_hp < 100) {
        tomatoMat.color.setHex(0xff4444);
    } else {
        tomatoMat.color.setHex(0x00C851);
    }
    
    // 同步 2D UI 面板
    document.getElementById('hp-value').innerText = data.tomato_hp;
    const statusEl = document.getElementById('status-text');
    statusEl.innerText = data.system_status;
    statusEl.className = data.tomato_hp < 100 ? 'danger' : 'safe';
};

// ================= 3. 渲染循环 =================
function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate();