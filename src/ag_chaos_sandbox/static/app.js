// 【封装】将场景创建逻辑封装成类，以便实例化两套独立的环境
class AgSandboxViewport {
    constructor(containerId, uiPrefix) {
        this.container = document.getElementById(containerId);
        this.uiPrefix = uiPrefix;

        this.scene = new THREE.Scene();
        this.scene.rotation.x = -Math.PI / 2; // 对齐 MuJoCo Z-up

        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        this.camera.position.set(0, 2, 2);
        this.camera.lookAt(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);

        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.maxPolarAngle = Math.PI / 2;

        const gridHelper = new THREE.GridHelper(4, 20);
        gridHelper.rotation.x = Math.PI / 2;
        this.scene.add(gridHelper);

        this.isPlantGenerated = false;
        this.currentAction = "None";
        this.armDir = new THREE.Vector3(1, 0, 0);

        this.initAssets();
    }

    createTextSprite(text) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        context.fillStyle = "rgba(0, 0, 0, 0.6)";
        context.roundRect(10, 10, 236, 108, 20);
        context.fill();
        context.font = "bold 45px sans-serif";
        context.fillStyle = "rgba(255, 255, 255, 1.0)";
        context.textAlign = "center";
        context.fillText(text, 128, 80);
        const texture = new THREE.CanvasTexture(canvas);
        const spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
        const sprite = new THREE.Sprite(spriteMat);
        sprite.scale.set(0.15, 0.075, 1.0);
        return sprite;
    }

    initAssets() {
        // 机械臂
        const eeGeo = new THREE.SphereGeometry(0.05, 16, 16);
        this.eeMat = new THREE.MeshBasicMaterial({ color: 0x888888 });
        this.eeMesh = new THREE.Mesh(eeGeo, this.eeMat);
        this.scene.add(this.eeMesh);

        const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 3 });
        this.armSkeletonLine = new THREE.Line(new THREE.BufferGeometry(), lineMat);
        this.scene.add(this.armSkeletonLine);

        // 植物群组
        this.plantGroup = new THREE.Group();
        this.scene.add(this.plantGroup);

        // 喷洒粒子
        this.sprayCount = 150;
        const sprayGeo = new THREE.BufferGeometry();
        this.sprayPos = new Float32Array(this.sprayCount * 3);
        this.sprayVel = [];
        for(let i=0; i<this.sprayCount; i++) {
            this.sprayPos[i*3] = 0; this.sprayPos[i*3+1] = 0; this.sprayPos[i*3+2] = 0;
            this.sprayVel.push({
                x: (Math.random() - 0.5) * 0.03,
                y: (Math.random() - 0.5) * 0.03,
                z: (Math.random() - 0.5) * 0.03
            });
        }
        sprayGeo.setAttribute('position', new THREE.BufferAttribute(this.sprayPos, 3));
        const sprayMat = new THREE.PointsMaterial({color: 0x00ffff, size: 0.015, transparent: true, opacity: 0.8});
        this.sprayParticles = new THREE.Points(sprayGeo, sprayMat);
        this.sprayParticles.visible = false;
        this.scene.add(this.sprayParticles);

        // 剪切物理光刃
        this.cutMat = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 3, transparent: true, opacity: 1 });
        const cutGeo = new THREE.BufferGeometry();
        this.cutLine = new THREE.LineSegments(cutGeo, this.cutMat);
        this.cutLine.visible = false;
        this.scene.add(this.cutLine);
    }

    resize() {
        if (!this.container.clientWidth || !this.container.clientHeight) return;
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    updateState(data) {
        if (!data) return;

        // 1. 生成植物 (仅一次)
        if (!this.isPlantGenerated && data.plant_structure) {
            const basePos = data.plant_structure.stem_base;
            this.plantGroup.position.set(basePos[0], basePos[1], basePos[2]);

            const stemGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.6);
            const stemMat = new THREE.MeshBasicMaterial({ color: 0x228B22 });
            const stemMesh = new THREE.Mesh(stemGeo, stemMat);
            stemMesh.rotation.x = Math.PI / 2;
            stemMesh.position.z = 0.3;
            this.plantGroup.add(stemMesh);

            data.plant_structure.tomatoes.forEach((t, index) => {
                const tGeo = new THREE.SphereGeometry(0.04);
                const tMat = new THREE.MeshBasicMaterial({ color: 0xff4444 });
                const tMesh = new THREE.Mesh(tGeo, tMat);
                tMesh.position.set(t[0], t[1], t[2]);
                this.plantGroup.add(tMesh);

                const label = this.createTextSprite(`番茄 ${index}`);
                label.position.set(t[0], t[1], t[2] + 0.06);
                this.plantGroup.add(label);
            });

            data.plant_structure.leaves.forEach(l => {
                const lGeo = new THREE.PlaneGeometry(0.12, 0.08);
                const lMat = new THREE.MeshBasicMaterial({ color: 0x32CD32, side: THREE.DoubleSide });
                const lMesh = new THREE.Mesh(lGeo, lMat);
                lMesh.position.set(l[0], l[1], l[2]);
                lMesh.lookAt(new THREE.Vector3(l[0]*2, l[1]*2, l[2]));
                this.plantGroup.add(lMesh);
            });

            this.isPlantGenerated = true;
        }

        // 2. 更新机械臂姿态
        if (data.arm_skeleton && data.arm_skeleton.length > 0) {
            const points = data.arm_skeleton.map(p => new THREE.Vector3(p[0], p[1], p[2]));
            this.armSkeletonLine.geometry.setFromPoints(points);
            this.eeMesh.position.copy(points[3]);
            this.armDir.subVectors(points[3], points[2]).normalize();
        }

        // 3. 动作反馈
        if (data.active_action === "Spray") {
            this.eeMat.color.setHex(0x00aaff);
        } else if (data.active_action === "Cut") {
            this.eeMat.color.setHex(0xff0000);
        } else {
            this.eeMat.color.setHex(0x888888);
        }

        this.currentAction = data.active_action;

        if (this.currentAction === "Cut" && !this.cutLine.visible) {
            this.cutLine.visible = true;
            this.cutMat.opacity = 1.0;
            const x = this.eeMesh.position.x, y = this.eeMesh.position.y, z = this.eeMesh.position.z;
            const s = 0.15;
            const offset = (Math.random() - 0.5) * 0.05;
            const pts = new Float32Array([
                x-s, y-s+offset, z,  x+s, y+s-offset, z,
                x-s, y+s+offset, z,  x+s, y-s-offset, z
            ]);
            this.cutLine.geometry.setAttribute('position', new THREE.BufferAttribute(pts, 3));
        }

        // 4. 更新 UI
        document.getElementById(`hp-${this.uiPrefix}`).innerText = data.tomato_hp;
        const statusEl = document.getElementById(`status-${this.uiPrefix}`);
        statusEl.innerText = data.system_status;
        statusEl.className = data.system_status.includes("❌") || data.system_status.includes("CRITICAL") || data.tomato_hp < 100 ? 'danger' : 'safe';
        document.getElementById(`dist-${this.uiPrefix}`).innerText = (data.current_target_dist * 100).toFixed(1);
    }

    render() {
        this.controls.update();

        // 喷洒粒子动画
        if (this.currentAction === "Spray") {
            this.sprayParticles.visible = true;
            const positions = this.sprayParticles.geometry.attributes.position.array;

            for(let i=0; i<this.sprayCount; i++) {
                positions[i*3]   += this.armDir.x * 0.08 + this.sprayVel[i].x;
                positions[i*3+1] += this.armDir.y * 0.08 + this.sprayVel[i].y;
                positions[i*3+2] += this.armDir.z * 0.08 + this.sprayVel[i].z - 0.005;

                const dx = positions[i*3] - this.eeMesh.position.x;
                const dy = positions[i*3+1] - this.eeMesh.position.y;
                const dz = positions[i*3+2] - this.eeMesh.position.z;

                if (dx*dx + dy*dy + dz*dz > 0.16 || Math.random() < 0.02) {
                    positions[i*3] = this.eeMesh.position.x;
                    positions[i*3+1] = this.eeMesh.position.y;
                    positions[i*3+2] = this.eeMesh.position.z;
                }
            }
            this.sprayParticles.geometry.attributes.position.needsUpdate = true;
        } else {
            this.sprayParticles.visible = false;
        }

        // 光刃动画
        if (this.currentAction === "Cut") {
            this.cutMat.opacity -= 0.02;
            if (this.cutMat.opacity <= 0) this.cutLine.visible = false;
        } else {
            this.cutLine.visible = false;
        }

        this.renderer.render(this.scene, this.camera);
    }
}

// ================= 实例化两个视口 =================
const vpNoRules = new AgSandboxViewport('canvas-no-rules', 'no-rules');
const vpRules = new AgSandboxViewport('canvas-rules', 'rules');

// ================= 窗口 Resize 与布局切换 =================
let isSingleView = false;
window.toggleViewMode = function() {
    isSingleView = !isSingleView;
    const vpNoRulesEl = document.getElementById('vp-no-rules');

    if (isSingleView) {
        vpNoRulesEl.classList.add('hidden'); // 隐藏对照组，只看有规则的
    } else {
        vpNoRulesEl.classList.remove('hidden');
    }

    // 稍等 DOM 渲染后再调整 Three.js canvas 尺寸
    setTimeout(() => {
        vpNoRules.resize();
        vpRules.resize();
    }, 350);
}

window.addEventListener('resize', () => {
    vpNoRules.resize();
    vpRules.resize();
});

// ================= WebSocket 通信 =================
const ws = new WebSocket(`ws://${window.location.host}/ws`);

window.sendAction = function(actionType) {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(actionType); // 指令会发给后端，后端分发到两个物理环境
    }
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    vpNoRules.updateState(data.env_no_rules);
    vpRules.updateState(data.env_rules);
};

// ================= 主渲染循环 =================
function animate() {
    requestAnimationFrame(animate);
    if (!isSingleView) vpNoRules.render();
    vpRules.render();
}
animate();
