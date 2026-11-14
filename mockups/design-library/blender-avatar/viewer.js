import * as THREE from '../vendor/three.module.min.js';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
const canvas=document.querySelector('#mascot'),stage=document.querySelector('#stage');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=false;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(34,1,.1,100);camera.position.set(0,2.55,8.5);camera.lookAt(0,1.55,0);if(location.pathname.endsWith('/embed.html')){camera.zoom=1.25;camera.updateProjectionMatrix();}
scene.add(new THREE.HemisphereLight(0xe9f0ff,0x977e69,2));
for(const [x,y,z,color,power] of [[-3,6,5,0xffe6d2,3],[4,3,3,0xc7d6ff,2],[-2,4,-3,0xffe1ba,3]]){const l=new THREE.DirectionalLight(color,power);l.position.set(x,y,z);l.castShadow=true;l.shadow.mapSize.set(1024,1024);l.shadow.camera.left=-4;l.shadow.camera.right=4;l.shadow.camera.top=5;l.shadow.camera.bottom=-3;scene.add(l);}
const shadowCanvas=document.createElement('canvas');shadowCanvas.width=128;shadowCanvas.height=128;const pen=shadowCanvas.getContext('2d'),gradient=pen.createRadialGradient(64,64,5,64,64,64);gradient.addColorStop(0,'rgba(75,55,48,.32)');gradient.addColorStop(1,'rgba(75,55,48,0)');pen.fillStyle=gradient;pen.fillRect(0,0,128,128);const floor=new THREE.Mesh(new THREE.PlaneGeometry(3.4,2.4),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(shadowCanvas),transparent:true,depthWrite:false}));floor.rotation.x=-Math.PI/2;floor.position.y=-.02;scene.add(floor);
const initialState=new URLSearchParams(location.search).get('state');
let mixer,state=['idle','thinking','correct','incorrect'].includes(initialState)?initialState:'idle',time=0,last=performance.now(),paused=false;
const still=document.querySelector('#still');still.checked=matchMedia('(prefers-reduced-motion: reduce)').matches;
const ranges={idle:[0,71/24],thinking:[89/24,185/24],correct:[209/24,245/24],incorrect:[269/24,317/24]};
const descriptions={idle:'Flutuação, respiração e piscadas.',thinking:'Inclinação curiosa e interrogação.',correct:'Salto e sorriso de comemoração; depois relaxa.',incorrect:'Pequena queda e expressão de oops; depois se recupera.'};
new GLTFLoader().load('parcel-buddy-reference-v3.glb?v=blue-front-2',g=>{scene.add(g.scene);g.scene.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});mixer=new THREE.AnimationMixer(g.scene);for(const clip of g.animations)mixer.clipAction(clip).play();document.querySelector('#fallback').hidden=true;},undefined,e=>{document.querySelector('#loading-message').textContent='Não foi possível carregar o modelo.';console.error(e);});
for(const b of document.querySelectorAll('[data-state]'))b.onclick=()=>{state=b.dataset.state;time=0;for(const btn of document.querySelectorAll('[data-state]'))btn.setAttribute('aria-pressed',String(btn===b));document.querySelector('#state-description').textContent=descriptions[state];};
document.querySelector('#replay').onclick=()=>time=0;
document.querySelector('#pause').onclick=e=>{paused=!paused;e.currentTarget.textContent=paused?'Continuar':'Pausar';e.currentTarget.setAttribute('aria-pressed',String(paused));};
new ResizeObserver(()=>{const r=stage.getBoundingClientRect();if(!r.width||!r.height)return;renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();}).observe(stage);
function frame(now){const dt=Math.min((now-last)/1000,.05);last=now;if(!paused&&!document.hidden&&!still.checked)time+=dt;if(mixer){let [start,end]=ranges[state],t=still.checked?.4:time;if((state==='correct'||state==='incorrect')&&t>end-start){[start,end]=ranges.idle;t-=ranges[state][1]-ranges[state][0];}mixer.setTime(start+(t%(end-start)));}renderer.render(scene,camera);requestAnimationFrame(frame);}requestAnimationFrame(frame);

// Only the same-origin parent can control an embedded instance.
window.addEventListener('message',event=>{
 if(event.origin!==location.origin||event.source!==window.parent||event.data?.type!=='quiz-avatar')return;
 const next=event.data.state;
 if(['idle','thinking','correct','incorrect'].includes(next)){state=next;time=0;}
 if(typeof event.data.paused==='boolean')paused=event.data.paused;
 if(typeof event.data.still==='boolean')still.checked=event.data.still;
});
