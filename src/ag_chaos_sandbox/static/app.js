// ================= 1. 初始化 Three.js 场景 =================
const scene = new THREE.Scene();
// 将 Three.js 世界翻转，彻底对齐 MuJoCo 的 Z-up 坐标系
scene.rotation.x = -Math.PI / 2;

const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
// 抬高camera，俯视整个沙盘
camera.position.set(0, 2, 2);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// 添加网格地面，帮助看清空间关系
const gridHelper = new THREE.GridHelper(4, 20);
gridHelper.rotation.x = Math.PI / 2;
scene.add(gridHelper);

// 资产 A：虚拟番茄 (绿色立方体)
const tomatoGeo = new THREE.BoxGeometry(0.1, 0.1, 0.1); // 稍微缩小一点方块，比例更协调
const tomatoMat = new THREE.MeshBasicMaterial({ color: 0x00C851 });
const tomatoMesh = new THREE.Mesh(tomatoGeo, tomatoMat);
scene.add(tomatoMesh);

// 资产 B：虚拟机械臂末端 (红色球体)
const eeGeo = new THREE.SphereGeometry(0.05, 16, 16);
const eeMat = new THREE.MeshBasicMaterial({ color: 0x888888 });
const eeMesh = new THREE.Mesh(eeGeo, eeMat);
scene.add(eeMesh);

// 资产 C：机械臂骨架连线（动态线条）
const lineGeo = new THREE.BufferGeometry();
const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 3 });
const armSkeletonLine = new THREE.Line(lineGeo, lineMat);
scene.add(armSkeletonLine)


// ================= 2. 建立 WebSocket 虚实通道 =================
const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // 1. 同步番茄位置（无需任何轴向换算）
    tomatoMesh.position.set(data.target_position[0], data.target_position[1], data.target_position[2]);

    // 2. 动态绘制机械臂的三维骨架线条
    if (data.arm_skeleton) {
        const points = data.arm_skeleton.map(p => new THREE.Vector3(p[0], p[1], p[2]));
        armSkeletonLine.geometry.setFromPoints(points);

        // 末端小球挂在最后一个骨架节点上
        const eePos = points[3];
        eeMesh.position.set(eePos.x, eePos.y, eePos.z);
    }

    // 3. 业务反馈：相撞变红
    if (data.tomato_hp < 90) {
        tomatoMat.color.setHex(0xff4444);
        eeMat.color.setHex(0xff0000);
    } else {
        tomatoMat.color.setHex(0x00C851);
        eeMat.color.setHex(0x888888);
    }

    // 4. UI 更新
    document.getElementById('hp-value').innerText = data.tomato_hp;
    const statusEl = document.getElementById('status-text');
    statusEl.innerText = data.system_status;
    statusEl.className = data.tomato_hp < 95 ? 'danger' : 'safe';
};

// ================= 3. 渲染循环 =================
function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate();