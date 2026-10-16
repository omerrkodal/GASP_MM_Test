import unreal
import json
from pathlib import Path

ASSET = '/Game/Blueprints/ControlRigs/CR_Prone'
NAME = 'Spine IK Test'
rig = unreal.EditorAssetLibrary.load_asset(ASSET)
editor = rig.get_editor_asset()
main = editor.get_model()
library = editor.get_local_function_library()
assert not any(n.get_name() == NAME for n in library.get_nodes()), 'Function already exists'
folder = Path(unreal.Paths.project_saved_dir()) / 'VibeUE' / 'ProneSpineIKTest'
folder.mkdir(parents=True, exist_ok=True)
run = json.loads(unreal.WorkflowService.start_run(NAME, json.dumps({'asset': ASSET, 'testing': 'user-owned'})))['runId']
(folder / 'run-id.txt').write_text(run)
mc = editor.get_controller(main)
(folder / 'main-before.txt').write_text(mc.export_nodes_to_text([n.get_name() for n in main.get_nodes()], False))
translation = next(g for g in library.get_contained_graphs(True) if g.get_outer().get_name().strip() == 'Translation Root')
from_world = next(n.get_script_struct().get_path_name() for n in translation.get_nodes() if n.get_name() == 'From World_1')
lc = editor.get_controller(library)
assert lc.open_undo_bracket('Add prone spine IK test')
try:
    fn = lc.add_function_to_library(NAME, True)
    assert fn
    print('CREATED:', ASSET, NAME)
    graph = fn.get_contained_graph()
    c = editor.get_controller(graph)
    assert c.add_exposed_pin('Alpha', unreal.RigVMPinDirection.INPUT, 'float', '', '1.000000')
    created = []
    def unit(name, path, x, y, defaults=None):
        node = c.add_unit_node_from_struct_path(path, 'Execute', unreal.Vector2D(x, y), name)
        assert node, name
        created.append(name)
        for pin, value in (defaults or {}).items():
            assert c.set_pin_default_value(name + '.' + pin, value), (name, pin)
        return node
    def math(name, kind, x, y, defaults=None):
        return unit(name, '/Script/RigVM.RigVMFunction_Math' + kind, x, y, defaults)
    def variable(name, variable_name, cpp_type, object_path, x, y):
        assert c.add_variable_node_from_object_path(variable_name, cpp_type, object_path, True, '', unreal.Vector2D(x, y), name)
        created.append(name)
    variable('Tip', 'Tip Data', 'FMoverFloorData', '/Script/Mover.MoverFloorData', -1600, 0)
    variable('Center', 'Center Data', 'FMoverFloorData', '/Script/Mover.MoverFloorData', -1600, 350)
    variable('Up', 'Actor Up Vector', 'FVector', '/Script/CoreUObject.Vector', -1600, 700)
    unit('MeshWorld', '/Script/ControlRig.RigUnit_ToWorldSpace_Transform', -1900, 1000)
    math('InverseMeshRotation', 'QuaternionInverse', -1600, 1000)
    for name, y in [('TipNormal', 200), ('CenterNormal', 500), ('ActorUp', 800)]:
        math(name, 'QuaternionRotateVector', -1250, y)
        math(name + 'Unit', 'VectorUnit', -1000, y)
    unit('TipPosition', from_world, -1250, -100)
    for name, bone, y in [('Root', 'root', 1150), ('Chest', 'spine_05', 1450), ('Base', 'spine_01', 1750)]:
        unit(name, '/Script/ControlRig.RigUnit_GetTransform', -1000, y,
             {'Item': '(Type=Bone,Name="' + bone + '")', 'Space': 'GlobalSpace', 'bInitial': 'False'})
    math('ChestFromRoot', 'VectorSub', -700, 600)
    math('PoseClearance', 'VectorDot', -400, 600)
    math('ChestFromTipPlane', 'VectorSub', -700, 0)
    math('TipPlaneDistance', 'VectorDot', -400, 0)
    math('ClearanceError', 'FloatSub', -100, 350)
    math('UpNormalDot', 'VectorDot', -700, 900)
    math('SafeUpNormalDot', 'FloatMax', -400, 900, {'B': '0.25'})
    math('HeightCorrection', 'FloatDiv', 200, 350)
    math('HeightOffset', 'VectorScale', 450, 350)
    math('ChestTarget', 'VectorAdd', 700, 350)
    math('TargetFromBase', 'VectorSub', 950, 350)
    math('CurrentReachVector', 'VectorSub', 700, 900)
    math('CurrentReach', 'VectorLength', 950, 900)
    math('ReachBoundedTarget', 'VectorClampLength', 1200, 350, {'MinimumLength': '0.0'})
    math('ReachableChestTarget', 'VectorAdd', 1450, 350)
    math('HasContacts', 'BoolAnd', 1200, -250)
    math('ContactAlpha', 'FloatSelectBool', 1450, -250, {'IfFalse': '0.0'})
    math('ClampAlpha', 'FloatClamp', 1700, -250, {'Minimum': '0.0', 'Maximum': '1.0'})
    unit('SpineCCD', '/Script/ControlRig.RigUnit_CCDIKItemArray', 2000, 350, {
        'Items': '(' + ','.join('(Type=Bone,Name="spine_%02d")' % i for i in range(1, 6)) + ')',
        'Precision': '0.01', 'MaxIterations': '12', 'bStartFromTail': 'True', 'bPropagateToChildren': 'True'})
    links = []
    def link(a, b):
        assert c.add_link(a, b), (a, b)
        links.append((a, b))
    link('MeshWorld.World.Rotation', 'InverseMeshRotation.Value')
    for name, source in [('TipNormal', 'Tip.Value.Normal'), ('CenterNormal', 'Center.Value.Normal'), ('ActorUp', 'Up.Value')]:
        link('InverseMeshRotation.Result', name + '.Transform')
        link(source, name + '.Vector')
        link(name + '.Result', name + 'Unit.Value')
    link('Tip.Value.Location', 'TipPosition.Value')
    link('Chest.Transform.Translation', 'ChestFromRoot.A')
    link('Root.Transform.Translation', 'ChestFromRoot.B')
    link('ChestFromRoot.Result', 'PoseClearance.A')
    link('CenterNormalUnit.Result', 'PoseClearance.B')
    link('Chest.Transform.Translation', 'ChestFromTipPlane.A')
    link('TipPosition.Global', 'ChestFromTipPlane.B')
    link('ChestFromTipPlane.Result', 'TipPlaneDistance.A')
    link('TipNormalUnit.Result', 'TipPlaneDistance.B')
    link('PoseClearance.Result', 'ClearanceError.A')
    link('TipPlaneDistance.Result', 'ClearanceError.B')
    link('ActorUpUnit.Result', 'UpNormalDot.A')
    link('TipNormalUnit.Result', 'UpNormalDot.B')
    link('UpNormalDot.Result', 'SafeUpNormalDot.A')
    link('ClearanceError.Result', 'HeightCorrection.A')
    link('SafeUpNormalDot.Result', 'HeightCorrection.B')
    link('ActorUpUnit.Result', 'HeightOffset.Value')
    link('HeightCorrection.Result', 'HeightOffset.Factor')
    link('Chest.Transform.Translation', 'ChestTarget.A')
    link('HeightOffset.Result', 'ChestTarget.B')
    link('ChestTarget.Result', 'TargetFromBase.A')
    link('Base.Transform.Translation', 'TargetFromBase.B')
    link('Chest.Transform.Translation', 'CurrentReachVector.A')
    link('Base.Transform.Translation', 'CurrentReachVector.B')
    link('CurrentReachVector.Result', 'CurrentReach.Value')
    link('TargetFromBase.Result', 'ReachBoundedTarget.Value')
    link('CurrentReach.Result', 'ReachBoundedTarget.MaximumLength')
    link('Base.Transform.Translation', 'ReachableChestTarget.A')
    link('ReachBoundedTarget.Result', 'ReachableChestTarget.B')
    link('Tip.Value.bDoesHit', 'HasContacts.A')
    link('Center.Value.bDoesHit', 'HasContacts.B')
    link('HasContacts.Result', 'ContactAlpha.Condition')
    link('Entry.Alpha', 'ContactAlpha.IfTrue')
    link('ContactAlpha.Result', 'ClampAlpha.Value')
    link('ClampAlpha.Result', 'SpineCCD.Weight')
    link('ReachableChestTarget.Result', 'SpineCCD.EffectorTransform.Translation')
    link('Chest.Transform.Rotation', 'SpineCCD.EffectorTransform.Rotation')
    link('Chest.Transform.Scale3D', 'SpineCCD.EffectorTransform.Scale3D')
    existing = [(l.get_source_pin().get_path_name(), l.get_target_pin().get_path_name()) for l in graph.get_links()]
    if any(a.endswith('.Entry.ExecuteContext') and b.endswith('.Return.ExecuteContext') for a, b in existing):
        assert c.break_link('Entry.ExecuteContext', 'Return.ExecuteContext')
    link('Entry.ExecuteContext', 'SpineCCD.ExecutePin')
    link('SpineCCD.ExecutePin', 'Return.ExecuteContext')
    call = mc.add_function_reference_node(fn, unreal.Vector2D(3210, 1450), NAME)
    assert call
    call_name = call.get_name()
    assert mc.set_pin_default_value(call_name + '.Alpha', '1.0')
    assert mc.break_link('Set Transform.ExecutePin', 'Foot IK Test.ExecuteContext')
    assert mc.add_link('Set Transform.ExecutePin', call_name + '.ExecuteContext')
    assert mc.add_link(call_name + '.ExecuteContext', 'Foot IK Test.ExecuteContext')
    assert lc.close_undo_bracket()
except Exception:
    lc.cancel_undo_bracket()
    unreal.WorkflowService.finish_run(run, 'partial', 'Function creation failed; edit undo bracket cancelled')
    raise
print('MODIFIED:', ASSET, 'root translation -> Spine IK Test -> foot IK')
log = Path(unreal.Paths.project_log_dir()) / 'GASP_MM_Test.log'
offset = log.stat().st_size
editor.recompile_vm()
assert unreal.EditorAssetLibrary.save_loaded_asset(rig, False)
prefix = graph.get_path_name() + '.'
actual = [(l.get_source_pin().get_path_name().removeprefix(prefix), l.get_target_pin().get_path_name().removeprefix(prefix)) for l in graph.get_links()]
assert all(pair in actual for pair in links)
mp = main.get_path_name() + '.'
main_links = [(l.get_source_pin().get_path_name().removeprefix(mp), l.get_target_pin().get_path_name().removeprefix(mp)) for l in main.get_links()]
assert ('Set Transform.ExecutePin', call_name + '.ExecuteContext') in main_links
assert (call_name + '.ExecuteContext', 'Foot IK Test.ExecuteContext') in main_links
with log.open('rb') as stream:
    stream.seek(offset)
    compile_log = stream.read().decode('utf-8', 'replace')
errors = [line for line in compile_log.splitlines() if any(t in line for t in ['LogRigVM: Error', 'LogControlRig: Error', 'LogRigVMCompiler: Error'])]
report = {'asset': ASSET, 'function': NAME, 'alpha': 1, 'chain': ['spine_%02d' % i for i in range(1, 6)], 'nodes': len(created), 'linksAudited': len(links), 'compiledAndSaved': True, 'compileErrors': errors, 'gameplayVerified': False,
          'rollback': {'removeCreatedFunction': NAME, 'removeCreatedCall': call_name, 'restoreLink': ['Set Transform.ExecutePin', 'Foot IK Test.ExecuteContext']}}
(folder / 'audit.json').write_text(json.dumps(report, indent=2))
(folder / 'compile-log.txt').write_text(compile_log)
(folder / 'function.txt').write_text(c.export_nodes_to_text([n.get_name() for n in graph.get_nodes()], False))
(folder / 'main-after.txt').write_text(mc.export_nodes_to_text([n.get_name() for n in main.get_nodes()], False))
for name in ['audit.json', 'main-before.txt', 'main-after.txt', 'compile-log.txt', 'function.txt']:
    unreal.WorkflowService.attach_run_artifact(run, str(folder / name), 'file')
unreal.WorkflowService.finish_run(run, 'partial' if errors else 'succeeded', 'Spine CCD IK test added with pose-derived clearance, reach-bounded target and contact-gated alpha. Compiled/saved and connections audited; gameplay testing left to user.')
print('AUDIT', json.dumps(report))
