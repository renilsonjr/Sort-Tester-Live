"""Reference-guided editable Blender mascot study; independent of production app."""
import bpy, math, os
from mathutils import Vector
from pathlib import Path
OUT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.fps=24
scene.world.color=(.25,.25,.25)
scene.view_settings.view_transform='AgX'
def mat(name,color,rough=.45,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 return m
# Linear-light values corresponding to the supplied reference palette.
def rgb(h):
 c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
 return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)
blue=mat('Reference • pearl blue E8F1FF',rgb('aacbf4'),.36)
ink=mat('Eye • deep plum',rgb('211c30'),.18)
iris=mat('Iris • warm amber',rgb('8f5036'),.3)
white=mat('Eye • catchlights',(1,1,1),.2)
blush=mat('Cheek • rose',rgb('ee9bb1'),.58)
boxmat=mat('Box • E3B267',rgb('e3b267'),.82)
tape=mat('Tape • F8E4B9',rgb('f8e4b9'),.65)
mouthmat=mat('Mouth • burgundy',rgb('4d2030'),.65)
tongue=mat('Tongue • coral',rgb('e9899b'),.48)
gold=mat('Sparkle • warm gold',rgb('ffd35b'),.3)
purple=mat('Thinking • violet',rgb('8752c9'),.4)
def empty(name,location=(0,0,0),parent=None):
 o=bpy.data.objects.new(name,None);scene.collection.objects.link(o);o.location=location;o.parent=parent;return o
root=empty('Mascot_ROOT')
def finish(o,name,material,parent=root):
 o.name=name;o.data.materials.append(material)
 for p in getattr(o.data,'polygons',[]):p.use_smooth=True
 o.parent=parent;return o
def sphere(name,loc,scale,material,parent=root):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=32,location=loc)
 o=finish(bpy.context.object,name,material,parent);o.scale=scale
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 return o
def cube(name,loc,scale,material,bevel=.045,parent=root):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=finish(bpy.context.object,name,material,parent);o.scale=scale
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 m=o.modifiers.new('Soft manufactured corners','BEVEL');m.width=bevel;m.segments=4
 o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');return o
def curve(name,points,radius,material,parent=root):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=24;c.bevel_depth=radius;c.bevel_resolution=5
 s=c.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
 for b,p in zip(s.bezier_points,points):b.co=p;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);o.data.materials.append(material);o.parent=parent;return o
body=sphere('Body • soft pear silhouette',(0,0,1.58),(1.10,.78,1.25),blue)
# Shape actual mesh: rounded crown, broader lower half; no feet.
for v in body.data.vertices:
 y=v.co.z/1.25;v.co.x*=1-.22*y;v.co.y*=1-.10*y
sub=body.modifiers.new('Silhouette polish','SUBSURF');sub.levels=1;sub.render_levels=1
face=empty('FACE_expressions',parent=root)
openeyes=[];closedeyes=[];brows=[]
for side in [-1,1]:
 x=side*.36
 eye=sphere(f'Eye_{side}',(x,-.719,2.09),(.145,.065,.225),ink,face);eye.rotation_euler.y=side*-.09;openeyes.append(eye)
 openeyes.append(sphere(f'Iris_{side}',(x,-.774,2.025),(.111,.018,.115),iris,face))
 openeyes.append(sphere(f'Pupil_{side}',(x,-.793,2.09),(.067,.012,.143),ink,face))
 openeyes.append(sphere(f'Highlight_large_{side}',(x-.037,-.814,2.18),(.046,.012,.065),white,face))
 openeyes.append(sphere(f'Highlight_small_{side}',(x+.052,-.812,2.03),(.019,.01,.023),white,face))
 closedeyes.append(curve(f'Joy_eye_{side}',[(x-.11,-.78,2.07),(x,-.80,2.15),(x+.11,-.78,2.07)],.021,ink,face))
 brows.append(curve(f'Brow_{side}',[(x-.105,-.65,2.40),(x,-.68,2.44),(x+.09,-.65,2.40)],.017,ink,face))
 for j in range(3):
  xx=x+side*.17+(j-1)*.05
  curve(f'Blush_{side}_{j}',[(xx-.015,-.72,1.88),(xx+.018,-.728,1.93)],.011,blush,face)
smile=curve('Mouth_neutral',[(-.155,-.79,1.83),(0,-.815,1.74),(.155,-.79,1.83)],.022,ink,face)
frown=curve('Mouth_oops',[(-.13,-.79,1.76),(0,-.815,1.84),(.13,-.79,1.76)],.023,ink,face)
happy=sphere('Mouth_cheer',(0,-.80,1.76),(.17,.025,.16),mouthmat,face)
happytongue=sphere('Tongue_cheer',(0,-.827,1.69),(.11,.012,.053),tongue,face)
parcel=empty('PACKAGE_detachable',parent=root)
cube('Cardboard box',(0,-1.02,1.12),(1.68,.63,.94),boxmat,.04,parcel)
cube('Tape top',(0,-1.02,1.596),(.24,.64,.013),tape,.006,parcel)
cube('Tape front',(0,-1.342,1.47),(.24,.012,.24),tape,.008,parcel)
# Fine lid seam rather than a printed brand mark.
seammat=mat('Box seam',rgb('b17d43'),.85)
cube('Lid seam',(0,-1.02,1.602),(1.65,.012,.006),seammat,.001,parcel)
arms=[]
for side in [-1,1]:
 pivot=empty(f'Arm_pivot_{side}',parent=root)
 curve(f'Arm_soft_{side}',[(side*.89,-.13,1.49),(side*1.08,-.51,1.18),(side*.91,-1.17,1.08)],.19,blue,pivot)
 sphere(f'Hand_{side}',(side*.89,-1.30,1.11),(.215,.16,.24),blue,pivot)
 arms.append(pivot)
# Reference punctuation, separate editable objects.
question=empty('Question_mark',parent=root)
curve('Question_curve',[(.95,-.10,2.78),(.96,-.1,2.95),(1.13,-.1,2.97),(1.18,-.1,2.85),(1.06,-.1,2.72),(1.06,-.1,2.64)],.035,purple,question)
sphere('Question_dot',(1.06,-.1,2.54),(.04,.035,.04),purple,question)
sparkles=empty('Celebration_sparkles',parent=root)
for i,(x,z) in enumerate([(-1.3,2.1),(-1.08,2.8),(1.24,2.63)]):
 verts=[(x,-.4,z+.17),(x+.045,-.4,z+.045),(x+.13,-.4,z),(x+.045,-.4,z-.045),(x,-.4,z-.17),(x-.045,-.4,z-.045),(x-.13,-.4,z),(x-.045,-.4,z+.045)]
 me=bpy.data.meshes.new('Sparkle');me.from_pydata(verts,[],[tuple(range(8))]);me.update();o=bpy.data.objects.new('Sparkle_'+str(i),me);scene.collection.objects.link(o);o.data.materials.append(gold);o.parent=sparkles
# Four self-contained action ranges, including facial scale keys for portable GLB animation.
ranges={'Idle':(1,72),'Thinking':(90,186),'Correct':(210,246),'Incorrect':(270,318)}
allanimated=[root,face,*openeyes,*closedeyes,*brows,smile,frown,happy,happytongue,question,sparkles,*arms]
base={o: (o.location.copy(),o.rotation_euler.copy(),o.scale.copy()) for o in allanimated}
def visible(o,on):o.scale=base[o][2] if on else Vector((.001,.001,.001))
def pose(name,u):
 for o,(loc,rot,scale) in base.items():o.location=loc;o.rotation_euler=rot;o.scale=scale
 root.location.z=.12+math.sin(u*math.tau)*.035
 correct=name=='Correct' and u<.88;incorrect=name=='Incorrect' and u<.75
 for o in openeyes:visible(o,not correct)
 for o in closedeyes:visible(o,correct)
 visible(smile,not correct and not incorrect and name!='Thinking');visible(frown,incorrect or name=='Thinking');visible(happy,correct);visible(happytongue,correct)
 visible(question,name=='Thinking');visible(sparkles,correct)
 if name=='Thinking':root.rotation_euler.y=.09+math.sin(u*math.tau)*.025;brows[0].rotation_euler.y=-.08
 if correct:root.location.z+=max(0,math.sin(u*math.pi))*.37;root.rotation_euler.y=math.sin(u*math.tau)*.04
 if incorrect:root.scale=(1.035,.99,.95);root.location.z=.075
 if name=='Idle' and .73<u<.82:
  for eye in openeyes:eye.scale.z*=.08
for name,(start,end) in ranges.items():
 scene.timeline_markers.new(name,frame=start)
 for f in range(start,end+1,3):
  pose(name,(f-start)/(end-start))
  for o in allanimated:
   for prop in ['location','rotation_euler','scale']:o.keyframe_insert(data_path=prop,frame=f)
scene.frame_start=1;scene.frame_end=318
# Shadow-catching warm studio floor and large softboxes.
floor=mat('Studio • warm ivory',rgb('f6eadd'),.9)
cube('Studio ground',(0,0,-.09),(200,200,.1),floor,.01,None)
def area(name,loc,power,size,color):
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.data.color=color;o.rotation_euler=(Vector((0,0,1.4))-o.location).to_track_quat('-Z','Y').to_euler()
area('Key • soft warm',(-3,-4,6),500,5,(1,.91,.82))
area('Fill • cool',(4,-2,4),350,4,(.77,.84,1))
area('Rim • pearl',(-2,3,4),650,3,(1,.88,.73))
bpy.ops.object.camera_add(location=(0,-9,2.65));camera=bpy.context.object;camera.rotation_euler=(Vector((0,-.2,1.55))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=4.65;scene.camera=camera
# Convert sculpted curves to portable meshes before GLB export.
for obj in list(bpy.data.objects):
 if obj.type=='CURVE':
  bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'parcel-buddy-reference-v3.blend'))
for name,frame in [('idle',1),('thinking',114),('correct',222),('incorrect',282)]:
 scene.frame_set(frame);scene.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
# Export only the character hierarchy; no lights, camera or studio floor.
bpy.ops.object.select_all(action='DESELECT')
def select_tree(o):
 o.select_set(True)
 for child in o.children:select_tree(child)
select_tree(root)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(OUT/'parcel-buddy-reference-v3.glb'),use_selection=True,export_format='GLB',export_animations=True,export_frame_range=True,export_cameras=False,export_lights=False)
print('AVATAR_BUILD_COMPLETE',OUT)
