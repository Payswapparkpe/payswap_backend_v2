import { Component, OnInit, OnDestroy, ElementRef } from '@angular/core';
import * as THREE from 'three';

/**
 * Forest Background Component
 * Three.js animated forest scene for home and auth pages
 */
@Component({
  selector: 'app-forest-background',
  standalone: true,
  template: '',
  styles: [`
    :host {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: -1;
      pointer-events: none;
    }
  `],
})
export class ForestBackgroundComponent implements OnInit, OnDestroy {
  private scene!: THREE.Scene;
  private camera!: THREE.PerspectiveCamera;
  private renderer!: THREE.WebGLRenderer;
  private animationId?: number;
  private trees: THREE.Mesh[] = [];
  private particles!: THREE.Points;
  private ground!: THREE.Mesh;
  private boundResize = this.onWindowResize.bind(this);

  constructor(private elementRef: ElementRef) {}

  ngOnInit() {
    this.initScene();
    this.createForest();
    this.animate();
  }

  ngOnDestroy() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
    }
    this.dispose();
  }

  private initScene() {
    // Scene setup – subtle ParkPe brand tint
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf5f3ff); // Very light violet/blue tint

    // Camera setup
    this.camera = new THREE.PerspectiveCamera(
      70,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    );
    this.camera.position.z = 28;
    this.camera.position.y = 8;

    // Renderer setup – alpha for subtle overlay when used on dark theme
    this.renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'low-power',
    });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.setAttribute('aria-hidden', 'true');
    this.elementRef.nativeElement.appendChild(this.renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 20, 10);
    this.scene.add(directionalLight);

    // Handle window resize
    window.addEventListener('resize', this.boundResize);
  }

  private createForest() {
    // Create simple tree shapes
    const treeGeometry = new THREE.ConeGeometry(2, 8, 8);
    const treeMaterial = new THREE.MeshPhongMaterial({ color: 0x004aad }); // ParkPe blue

    const trunkGeometry = new THREE.CylinderGeometry(0.5, 0.7, 3, 8);
    const trunkMaterial = new THREE.MeshPhongMaterial({ color: 0x5d4037 }); // Brown

    // Create multiple trees in a forest pattern
    for (let i = 0; i < 30; i++) {
      const tree = new THREE.Group();

      // Trunk
      const trunk = new THREE.Mesh(trunkGeometry, trunkMaterial);
      trunk.position.y = 1.5;
      tree.add(trunk);

      // Foliage
      const foliage = new THREE.Mesh(treeGeometry, treeMaterial);
      foliage.position.y = 5;
      tree.add(foliage);

      // Random positioning
      tree.position.x = (Math.random() - 0.5) * 60;
      tree.position.z = (Math.random() - 0.5) * 60;
      tree.position.y = 0;

      // Random rotation
      tree.rotation.y = Math.random() * Math.PI * 2;

      // Random scale for variety
      const scale = 0.8 + Math.random() * 0.4;
      tree.scale.set(scale, scale, scale);

      this.trees.push(tree);
      this.scene.add(tree);
    }

    // Add ground
    const groundGeometry = new THREE.PlaneGeometry(100, 100);
    const groundMaterial = new THREE.MeshPhongMaterial({
      color: 0xdbe8ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    this.ground = new THREE.Mesh(groundGeometry, groundMaterial);
    this.ground.rotation.x = -Math.PI / 2;
    this.ground.position.y = 0;
    this.scene.add(this.ground);

    // Add particles for atmosphere
    this.addParticles();
  }

  private addParticles() {
    const particlesGeometry = new THREE.BufferGeometry();
    const particlesCount = 100;
    const positions = new Float32Array(particlesCount * 3);

    for (let i = 0; i < particlesCount * 3; i++) {
      positions[i] = (Math.random() - 0.5) * 100;
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const particlesMaterial = new THREE.PointsMaterial({
      size: 0.25,
      color: 0xffffff,
      transparent: true,
      opacity: 0.35,
    });

    this.particles = new THREE.Points(particlesGeometry, particlesMaterial);
    this.scene.add(this.particles);
  }

  private animate() {
    this.animationId = requestAnimationFrame(() => this.animate());

    // Very subtle camera drift for high-end feel
    const time = Date.now() * 0.00008;
    this.camera.position.x = Math.sin(time) * 2;
    this.camera.lookAt(0, 4, 0);

    // Gentle tree sway
    this.trees.forEach((tree, index) => {
      tree.rotation.z = Math.sin(time + index * 0.5) * 0.03;
    });

    this.renderer.render(this.scene, this.camera);
  }

  private onWindowResize() {
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }

  private dispose() {
    window.removeEventListener('resize', this.boundResize);

    this.scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        const mat = obj.material;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else mat.dispose();
      }
    });
    if (this.particles) {
      this.particles.geometry.dispose();
      (this.particles.material as THREE.Material).dispose();
    }
    if (this.ground) {
      this.ground.geometry.dispose();
      (this.ground.material as THREE.Material).dispose();
    }

    if (this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
    this.renderer.dispose();
  }
}
