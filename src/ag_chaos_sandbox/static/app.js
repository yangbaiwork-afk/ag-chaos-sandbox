const scene = new THREE.Scene();
scene.rotation.x = -Math.PI / 2; // 对齐 MuJoCo Z-up

const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
camera.position.set(0, 2, 2);
camera.lookAt(0, 0, 0);

// ================= 核心修复：必须先初始化 Renderer =================
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// ================= 然后才能将 renderer 传给 OrbitControls =================
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; // 开启阻尼（惯性），让滑动视角更丝滑
controls.dampingFactor = 0.05;
controls.maxPolarAngle = Math.PI / 2; // 禁止摄像机钻到地底下

const gridHelper = new THREE.GridHelper(4, 20);
gridHelper.rotation.x = Math.PI / 2;
scene.add(gridHelper);

// 【新增】黑科技：用 Canvas 动态生成永远朝向摄像机的 3D 文字铭牌
function createTextSprite(text) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 128;
    const context = canvas.getContext('2d');

    // 画背景框
    context.fillStyle = "rgba(0, 0, 0, 0.6)";
    context.roundRect(10, 10, 236, 108, 20);
    context.fill();

    // 画文字
    context.font = "bold 45px sans-serif";
    context.fillStyle = "rgba(255, 255, 255, 1.0)";
    context.textAlign = "center";
    context.fillText(text, 128, 80);

    const texture = new THREE.CanvasTexture(canvas);
    const spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
    const sprite = new THREE.Sprite(spriteMat);
    sprite.scale.set(0.15, 0.075, 1.0); // 调整铭牌大小
    return sprite;
}


// ================= 1. 资产初始化 =================
// 机械臂
const eeGeo = new THREE.SphereGeometry(0.05, 16, 16);
const eeMat = new THREE.MeshBasicMaterial({ color: 0x888888 });
const eeMesh = new THREE.Mesh(eeGeo, eeMat);
scene.add(eeMesh);

const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 3 });
const armSkeletonLine = new THREE.Line(new THREE.BufferGeometry(), lineMat);
scene.add(armSkeletonLine);

// 用于存储动态生成的植物群组
const plantGroup = new THREE.Group();
scene.add(plantGroup);
let isPlantGenerated = false;

// ================= 【新增】特效资产 A：喷洒雾化粒子 =================
const sprayCount = 150;
const sprayGeo = new THREE.BufferGeometry();
const sprayPos = new Float32Array(sprayCount * 3);
const sprayVel = []; // 记录每个粒子的初始扩散速度
for(let i=0; i<sprayCount; i++) {
    sprayPos[i*3] = 0; sprayPos[i*3+1] = 0; sprayPos[i*3+2] = 0;
    // 生成圆锥体扩散速度场（为后期的风场干扰做准备）
    sprayVel.push({
        x: (Math.random() - 0.5) * 0.03,
        y: (Math.random() - 0.5) * 0.03,
        z: (Math.random() - 0.5) * 0.03 // 由于画面翻转，Z轴负方向为重力下坠方向
    });
}
// 新增全局变量记录机械臂指向
let armDir = new THREE.Vector3(1, 0, 0);

sprayGeo.setAttribute('position', new THREE.BufferAttribute(sprayPos, 3));
const sprayMat = new THREE.PointsMaterial({color: 0x00ffff, size: 0.015, transparent: true, opacity: 0.8});
const sprayParticles = new THREE.Points(sprayGeo, sprayMat);
sprayParticles.visible = false;
scene.add(sprayParticles);

// ================= 【新增】特效资产 B：剪切物理光刃 =================
const cutMat = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 3, transparent: true, opacity: 1 });
const cutGeo = new THREE.BufferGeometry();
const cutLine = new THREE.LineSegments(cutGeo, cutMat);
cutLine.visible = false;
scene.add(cutLine);

// 用于记录前端当前的动作状态
let currentAction = "None";

// ================= 2. 通信与交互 =================
const ws = new WebSocket(`ws://${window.location.host}/ws`);

// 暴露给 HTML 按钮调用的全局函数
window.sendAction = function(actionType) {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(actionType);
    }
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    // 1. 初次连接时，根据后端数据生成整棵植物
    if (!isPlantGenerated && data.plant_structure) {
        const basePos = data.plant_structure.stem_base;
        plantGroup.position.set(basePos[0], basePos[1], basePos[2]);

        // 画主茎
        const stemGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.6);
        const stemMat = new THREE.MeshBasicMaterial({ color: 0x228B22 });
        const stemMesh = new THREE.Mesh(stemGeo, stemMat);
        stemMesh.rotation.x = Math.PI / 2;
        stemMesh.position.z = 0.3;
        plantGroup.add(stemMesh);

        // 画番茄
        data.plant_structure.tomatoes.forEach((t, index) => {
            const tGeo = new THREE.SphereGeometry(0.04);
            const tMat = new THREE.MeshBasicMaterial({ color: 0xff4444 });
            const tMesh = new THREE.Mesh(tGeo, tMat);
            tMesh.position.set(t[0], t[1], t[2]);
            plantGroup.add(tMesh);

            // 【新增】给番茄挂上 3D 铭牌，高度提高 0.06 米悬浮
            const label = createTextSprite(`番茄 ${index}`);
            label.position.set(t[0], t[1], t[2] + 0.06);
            plantGroup.add(label);
        });

        // 画叶片
        data.plant_structure.leaves.forEach(l => {
            const lGeo = new THREE.PlaneGeometry(0.12, 0.08); // 用平面代表叶子
            const lMat = new THREE.MeshBasicMaterial({ color: 0x32CD32, side: THREE.DoubleSide });
            const lMesh = new THREE.Mesh(lGeo, lMat);
            lMesh.position.set(l[0], l[1], l[2]);
            // 让叶片稍微朝向外侧
            lMesh.lookAt(new THREE.Vector3(l[0]*2, l[1]*2, l[2]));
            plantGroup.add(lMesh);
        });

        isPlantGenerated = true;
    }

    // 2. 更新机械臂姿态
    if (data.arm_skeleton.length > 0) {
        const points = data.arm_skeleton.map(p => new THREE.Vector3(p[0], p[1], p[2]));
        armSkeletonLine.geometry.setFromPoints(points);
        eeMesh.position.copy(points[3]);
        // 【新增】利用倒数第二个关节和末端坐标，计算出枪口的绝对向量朝向
        armDir.subVectors(points[3], points[2]).normalize();
    }

    // 3. 动作反馈：喷洒时让末端变成蓝色，剪切变成红色
    if (data.active_action === "Spray") {
        eeMat.color.setHex(0x00aaff); // 蓝色代表水雾
        // TODO: 后续可在这里添加 Three.js 粒子效果
    } else if (data.active_action === "Cut") {
        eeMat.color.setHex(0xff0000); // 红色代表危险剪切
    } else {
        eeMat.color.setHex(0x888888);
    }

    // 同步后端动作状态
    currentAction = data.active_action;

    // 【新增】如果触发了剪切动作，在机械臂末端生成一个 X 型光刃
    if (currentAction === "Cut" && !cutLine.visible) {
        cutLine.visible = true;
        cutMat.opacity = 1.0;
        const x = eeMesh.position.x, y = eeMesh.position.y, z = eeMesh.position.z;
        const s = 0.15;

        // 【修改】每次剪切，光刃稍微有些随机偏移，显得更像物理动作
        const offset = (Math.random() - 0.5) * 0.05;
        const pts = new Float32Array([
            x-s, y-s+offset, z,  x+s, y+s-offset, z,
            x-s, y+s+offset, z,  x+s, y-s-offset, z
        ]);
        cutLine.geometry.setAttribute('position', new THREE.BufferAttribute(pts, 3));
    }

    // 4. 更新 UI
    document.getElementById('hp-value').innerText = data.tomato_hp;
    const statusEl = document.getElementById('status-text');
    statusEl.innerText = data.system_status;
    statusEl.className = data.system_status.includes("❌") || data.tomato_hp < 100 ? 'danger' : 'safe';
    // 【新增】更新雷达距离 (转换为 cm 并保留一位小数)
    document.getElementById('dist-value').innerText = (data.current_target_dist * 100).toFixed(1);
};

function animate() {
    requestAnimationFrame(animate);
    controls.update();

    // 【新增】驱动喷洒粒子流动
    // 【修复】驱动喷洒粒子沿枪口飞出
    if (currentAction === "Spray") {
        sprayParticles.visible = true;
        const positions = sprayParticles.geometry.attributes.position.array;

        for(let i=0; i<sprayCount; i++) {
            // 顺着枪口方向 (armDir) 高速飞出，加上粒子的随机扰动和微弱重力 (-0.005)
            positions[i*3]   += armDir.x * 0.08 + sprayVel[i].x;
            positions[i*3+1] += armDir.y * 0.08 + sprayVel[i].y;
            positions[i*3+2] += armDir.z * 0.08 + sprayVel[i].z - 0.005;

            // 计算飞出的距离
            const dx = positions[i*3] - eeMesh.position.x;
            const dy = positions[i*3+1] - eeMesh.position.y;
            const dz = positions[i*3+2] - eeMesh.position.z;

            // 只要飞出超过 0.4 米，或者随机寿命终结，就在枪口重生
            if (dx*dx + dy*dy + dz*dz > 0.16 || Math.random() < 0.02) {
                positions[i*3] = eeMesh.position.x;
                positions[i*3+1] = eeMesh.position.y;
                positions[i*3+2] = eeMesh.position.z;
            }
        }
        sprayParticles.geometry.attributes.position.needsUpdate = true;
    } else {
        sprayParticles.visible = false;
    }

    // 【新增】驱动光刃淡出动画
    if (currentAction === "Cut") {
        cutMat.opacity -= 0.02; // 随着时间淡出
        if (cutMat.opacity <= 0) cutLine.visible = false;
    } else {
        cutLine.visible = false;
    }

    renderer.render(scene, camera);
}

animate();