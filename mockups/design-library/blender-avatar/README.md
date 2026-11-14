# Avatar Blender v3

Reference-guided 3D model study created with Blender 5.3.0. Previous avatar previews were removed at the owner’s request; the production app is unchanged. See [[2026-11-14-visual-library-design]].

- `parcel-buddy-reference-v3.blend`: editable geometry, materials, studio, camera and object animation keys.
- `parcel-buddy-reference-v3.glb`: character hierarchy and baked animation tracks, approximately 1.3 MB.
- `idle.png`, `thinking.png`, `correct.png`, `incorrect.png`: Cycles studio renders.
- `index.html`, `viewer.js`: browser review with four segment controls.
- `build_avatar.py`: reproducible construction/render/export script. Re-running overwrites the generated model and render outputs.

Open `http://127.0.0.1:8014/mockups/design-library/blender-avatar/` while serving the repository root. The supplied reference is preserved at `../avatar-reference.png`.

## Animation

24 fps; Idle frames 1–72, Thinking 90–186, Correct 210–246, Incorrect 270–318. The GLB contains synchronized object tracks on one timeline; the viewer selects these ranges. These are not four independent skeletal clips. The model has no production skeletal rig, facial morph rig or retopology pass. Arms are modeled but do not yet reproduce the raised-hand cheer in the reference. This is a closer visual study, not an exact reconstruction or a claim of production readiness.

## Verification

Blender headless build completed successfully, saved the blend file, rendered four poses and exported GLB. Idle render visually inspected. GLB loaded in Chrome without observed console errors; all four state controls were exercised. Browser lighting approximates the studio render. Material colors and geometric proportions remain adjustable; displayed swatches describe the supplied reference palette.
