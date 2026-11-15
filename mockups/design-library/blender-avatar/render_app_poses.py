"""Re-render the approved avatar poses on a warm backdrop.

Opens the approved .blend read-only, changes only the world colour, and
writes the four poses elsewhere. It never saves the .blend or the .glb, so
the approved model is untouched.
"""
import bpy, sys
from pathlib import Path

blend, out = sys.argv[-2], Path(sys.argv[-1])
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
# The app's warm surface (#fffdf8), in the linear values Blender expects.
WARM = (1.0, 0.982, 0.940, 1.0)
world = scene.world
world.color = WARM[:3]
# A world that uses nodes ignores world.color, so set the background node too.
if world.use_nodes and world.node_tree:
    for node in world.node_tree.nodes:
        if node.type == 'BACKGROUND':
            node.inputs['Color'].default_value = WARM
            node.inputs['Strength'].default_value = 3.0
            print('background node set')
scene.render.film_transparent = False
for name, frame in (('idle', 1), ('thinking', 114), ('correct', 222), ('incorrect', 282)):
    scene.frame_set(frame)
    scene.render.filepath = str(out / f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print('rendered', name)
