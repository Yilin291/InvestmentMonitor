import React, {useEffect, useRef, useState} from 'react';
const shapeBox=(T,w,h,r)=>{
  const s=new T.Shape(),x=-w/2,y=-h/2;
  s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);
  s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);
  s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;
};

export function SnowballRobot({state='idle', compact=false}){
  const host=useRef(null),sceneWake=useRef(()=>{}),stateRef=useRef(state);
  const [fallback,setFallback]=useState(false);
  stateRef.current=state;

  useEffect(()=>{
    const wrap=host.current;if(!wrap)return;
    let disposed=false,teardown=()=>{};
    const start=async()=>{
    const T=await import('../vendor/three.module.js');
    if(disposed)return;
    let renderer;
    try{
      renderer=new T.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
    }catch{
      setFallback(true);return;
    }
    const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.1,40);
    camera.position.set(0,.14,6.45);camera.lookAt(0,.02,0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
    renderer.outputColorSpace=T.SRGBColorSpace;
    renderer.toneMapping=T.ACESFilmicToneMapping;
    renderer.toneMappingExposure=1.08;
    wrap.prepend(renderer.domElement);
    renderer.domElement.setAttribute('aria-hidden','true');
    scene.add(new T.HemisphereLight(0xeafaff,0x466276,2.6));
    for(const [color,intensity,x,y,z] of [[0xffffff,4,-3,5,4],[0x77dfff,3,3,1,3],[0xa1baff,2,-3,0,-2]]){
      const light=new T.DirectionalLight(color,intensity);light.position.set(x,y,z);scene.add(light);
    }
    const shell=new T.MeshPhysicalMaterial({color:0x51b9e1,metalness:.35,roughness:.24,clearcoat:1,clearcoatRoughness:.14});
    const rim=new T.MeshPhysicalMaterial({color:0xa9dce8,metalness:.64,roughness:.22,clearcoat:1,clearcoatRoughness:.12});
    const white=new T.MeshPhysicalMaterial({color:0xf4f6f5,metalness:.12,roughness:.28,clearcoat:.8});
    const metal=new T.MeshStandardMaterial({color:0x9eafba,metalness:.83,roughness:.26});
    const dark=new T.MeshPhysicalMaterial({color:0x081528,metalness:.26,roughness:.17,clearcoat:1,clearcoatRoughness:.08});
    const rubber=new T.MeshStandardMaterial({color:0x1b2b3e,roughness:.65});
    const orange=new T.MeshStandardMaterial({color:0xffaf45,metalness:.25,roughness:.35});
    const ice=new T.MeshStandardMaterial({color:0x69eaff,emissive:0x14caff,emissiveIntensity:1.7,roughness:.25});
    const halo=new T.MeshBasicMaterial({color:0x42cefa,transparent:true,opacity:.19,depthWrite:false,blending:T.AdditiveBlending});
    const glow=new T.MeshBasicMaterial({color:0x57dcff,transparent:true,opacity:.095,depthWrite:false,blending:T.AdditiveBlending});
    const reflection=new T.MeshBasicMaterial({color:0xe8fbff,transparent:true,opacity:.3,depthWrite:false});
    const materials=[shell,rim,white,metal,dark,rubber,orange,ice,halo,glow,reflection];
    const root=new T.Group(),head=new T.Group();scene.add(root);root.add(head);
    const makeMesh=(parent,geometry,material,pos=[0,0,0])=>{const m=new T.Mesh(geometry,material);m.position.set(...pos);parent.add(m);return m;};
    const ellipsoid=(parent,material,x,y,z,sx,sy,sz)=>{const m=makeMesh(parent,new T.SphereGeometry(1,40,28),material,[x,y,z]);m.scale.set(sx,sy,sz);return m;};
    const plate=(parent,shape,material,depth,bevel,pos)=>makeMesh(parent,new T.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:bevel,bevelThickness:bevel,curveSegments:20}),material,pos);

    ellipsoid(head,shell,0,.27,0,1.05,.77,.7);
    const dome=makeMesh(head,new T.SphereGeometry(1,40,24,0,Math.PI*2,0,Math.PI/2),white,[0,.72,0]);dome.scale.set(.83,.36,.59);
    const lid=makeMesh(head,new T.TorusGeometry(.72,.024,10,64),metal,[0,.74,0]);lid.rotation.x=Math.PI/2;lid.scale.y=.77;
    plate(head,shapeBox(T,1.78,.96,.31),rubber,.035,.07,[0,.2,.525]);
    plate(head,shapeBox(T,1.74,.92,.3),shell,.04,.075,[0,.2,.56]);
    plate(head,shapeBox(T,1.58,.78,.255),rim,.025,.052,[0,.22,.626]);
    plate(head,shapeBox(T,1.5,.7,.235),dark,.024,.055,[0,.22,.655]);
    plate(head,shapeBox(T,.4,.12,.045),rubber,.016,.02,[0,-.185,.68]);
    for(const x of [-.59,.59]){const bolt=makeMesh(head,new T.CylinderGeometry(.025,.025,.012,20),metal,[x,.2,.701]);bolt.rotation.x=Math.PI/2;}
    const glint=plate(head,shapeBox(T,.39,.022,.01),reflection,.001,.001,[-.38,.49,.699]);glint.rotation.z=.07;
    const seam=makeMesh(head,new T.TorusGeometry(.68,.009,8,80,Math.PI),rim,[0,.72,.04]);seam.rotation.set(Math.PI/2,0,Math.PI);

    const eyes=[],eyeRig=new T.Group();head.add(eyeRig);eyeRig.position.set(0,.23,.721);
    for(const side of [-1,1]){
      const eye=new T.Group();eye.position.x=side*.28;eyeRig.add(eye);eyes.push(eye);
      plate(eye,shapeBox(T,.19,.4,.09),halo,.003,.018,[0,0,-.014]);
      plate(eye,shapeBox(T,.12,.3,.058),ice,.012,.026,[0,0,.006]);
      plate(eye,shapeBox(T,.026,.16,.013),reflection,.002,.006,[side*-.018,.015,.027]);
    }

    const ears=[];
    for(const side of [-1,1]){
      const ear=new T.Group();ear.position.set(side*.91,.69,-.035);ear.scale.set(side*.72,.76,.92);head.add(ear);ears.push(ear);
      const hinge=makeMesh(ear,new T.CylinderGeometry(.067,.067,.135,24),metal);hinge.rotation.z=Math.PI/2;
      const pivot=makeMesh(ear,new T.TorusGeometry(.073,.012,8,24),rim);pivot.rotation.y=Math.PI/2;
      const wing=new T.Shape();wing.moveTo(.015,.025);wing.bezierCurveTo(.18,.19,.43,.18,.62,-.015);wing.bezierCurveTo(.45,.025,.22,-.045,.045,-.08);wing.closePath();
      plate(ear,wing,shell,.16,.045,[0,0,-.06]);
      const inset=new T.Shape();inset.moveTo(.08,.035);inset.bezierCurveTo(.23,.13,.4,.12,.51,.015);inset.bezierCurveTo(.37,.035,.24,-.005,.1,-.03);inset.closePath();
      plate(ear,inset,rim,.006,.012,[0,0,.105]);
      const brace=makeMesh(ear,new T.CylinderGeometry(.018,.018,.29,12),metal,[.19,-.115,-.005]);brace.rotation.z=-.36;
    }

    ellipsoid(root,rubber,0,-.48,-.05,.66,.31,.45);
    for(const side of [-1,1]){plate(root,shapeBox(T,.13,.095,.03),orange,.035,.025,[side*.62,-.34,.35]);ellipsoid(root,metal,side*.82,-.13,.2,.075,.1,.1);}
    const jets=[];
    for(const [x,y,z,scale] of [[-.52,-.66,-.04,.72],[.52,-.66,-.04,.72],[0,-.72,.34,1]]){
      const pod=new T.Group();pod.position.set(x,y,z);pod.scale.setScalar(scale);pod.rotation.x=-.45;root.add(pod);
      makeMesh(pod,new T.CylinderGeometry(.17,.225,.34,32),metal);
      const collar=makeMesh(pod,new T.TorusGeometry(.185,.024,10,36),rim,[0,-.15,0]);collar.rotation.x=Math.PI/2;
      const ring=makeMesh(pod,new T.TorusGeometry(.19,.032,10,36),shell,[0,-.18,0]);ring.rotation.x=Math.PI/2;
      const emitter=makeMesh(pod,new T.CircleGeometry(.15,36),ice,[0,-.204,0]);emitter.rotation.x=Math.PI/2;
      const jet=makeMesh(pod,new T.ConeGeometry(.125,.54,28,1,true),glow,[0,-.5,0]);jet.rotation.z=Math.PI;jets.push(jet);
    }

    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
    let raf=0,visible=true,last=0,started=performance.now(),stateAt=started,previousState=stateRef.current;
    let lookX=0,lookY=0,currentX=0,currentY=0;
    const resize=()=>{const rect=wrap.getBoundingClientRect();if(!rect.width||!rect.height)return;renderer.setSize(rect.width,rect.height,false);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();wake();};
    const frame=now=>{
      raf=0;if(disposed||!visible||document.hidden)return;
      if(!reduced.matches&&now-last<32){raf=requestAnimationFrame(frame);return;}
      last=now;
      const current=stateRef.current;if(current!==previousState){previousState=current;stateAt=now;}
      const elapsed=(now-started)/1000,phase=(now-stateAt)/1000,moving=!reduced.matches;
      currentX+=(lookX-currentX)*.16;currentY+=(lookY-currentY)*.16;
      root.position.y=moving?Math.sin(elapsed*1.7)*.055:0;root.rotation.z=moving?Math.sin(elapsed*.9)*.018:0;
      head.rotation.y=moving?currentX*.17:0;head.rotation.x=moving?-currentY*.08:0;
      head.rotation.z=moving&&current==='question'?.09:0;
      if(moving&&current==='success'&&phase<1.2)head.rotation.x+=Math.sin(phase*7)*.07;
      eyeRig.position.x=moving?currentX*.13:0;eyeRig.position.y=.23+(moving?currentY*.075:0);
      const blink=moving&&elapsed%5.4>5.21?.14:1;
      eyes.forEach((eye,i)=>{eye.scale.y=current==='success'?.55:current==='thinking'?(i===0?.8:.6):blink;eye.rotation.z=current==='question'?(i===0?-.11:.11):0;});
      ears.forEach((ear,i)=>{const side=i===0?-1:1;ear.rotation.z=moving?side*(.025+Math.sin(elapsed*1.8+i*.8)*.045+(current==='listening'?.12:current==='question'?.1:0)):0;ear.rotation.x=moving?Math.sin(elapsed*1.4+i)*.045:0;});
      jets.forEach((jet,i)=>{jet.scale.y=moving?1+Math.sin(elapsed*4+i)*.1:1;});
      ice.emissiveIntensity=current==='thinking'&&moving?1.8+Math.sin(elapsed*4)*.25:1.7;
      ice.color.set(current==='error'?0xffc582:0x69eaff);
      renderer.render(scene,camera);
      if(moving)raf=requestAnimationFrame(frame);
    };
    const wake=()=>{if(!disposed&&!raf&&visible&&!document.hidden)raf=requestAnimationFrame(frame);};sceneWake.current=wake;
    const pointer=e=>{if(reduced.matches||e.pointerType==='touch')return;const rect=wrap.getBoundingClientRect();lookX=T.MathUtils.clamp((e.clientX-rect.left-rect.width/2)/Math.max(innerWidth*.35,rect.width),-1,1);lookY=T.MathUtils.clamp(-(e.clientY-rect.top-rect.height/2)/Math.max(innerHeight*.35,rect.height),-1,1);wake();};
    const leave=()=>{lookX=0;lookY=0;wake();};
    const visibility=()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else wake();};
    const observer=new ResizeObserver(resize);observer.observe(wrap);
    const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)wake();else{cancelAnimationFrame(raf);raf=0;}});intersection.observe(wrap);
    window.addEventListener('pointermove',pointer,{passive:true});document.documentElement.addEventListener('pointerleave',leave);document.addEventListener('visibilitychange',visibility);
    reduced.addEventListener?.('change',wake);
    resize();
    teardown=()=>{cancelAnimationFrame(raf);observer.disconnect();intersection.disconnect();window.removeEventListener('pointermove',pointer);document.documentElement.removeEventListener('pointerleave',leave);document.removeEventListener('visibilitychange',visibility);reduced.removeEventListener?.('change',wake);scene.traverse(o=>o.geometry?.dispose());materials.forEach(m=>m.dispose());renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();sceneWake.current=()=>{};};
    };
    start().catch(()=>setFallback(true));
    return ()=>{disposed=true;teardown();};
  },[]);
  useEffect(()=>{sceneWake.current();},[state]);
  return <div ref={host} className={`snowball-robot${compact?' compact':''}${fallback?' fallback':''}`} role="img" aria-label="悬浮的雪球风格监控助手；电子眼会随鼠标移动。">{fallback&&<div className="snowball-fallback" aria-hidden="true"><i/><i/><b/><span/></div>}</div>;
}
